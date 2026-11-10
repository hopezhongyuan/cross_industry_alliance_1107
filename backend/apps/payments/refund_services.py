"""退款服务：未结算订单的退款、记账与订单状态联动。

已结算订单的退款（可提现/佣金冲回）留在 M3。
"""

from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError
from apps.ledger.constants import AccountType, Direction
from apps.ledger.models import SettlementItem
from apps.ledger.services import post_transaction
from apps.orders.models import Order
from apps.orders.order_services import restore_order_resources
from apps.orders.services import transit_order
from apps.orders.split_services import apply_refund

from .models import PaymentOrder, RefundOrder, default_refund_no
from .providers import refund_payment

Funding = SimpleNamespace(MERCHANT="MERCHANT", PLATFORM="PLATFORM")


def refund_order(
    order_id: int,
    amount: int,
    reason: str,
    after_sale=None,
    reject_event=None,
    approve_event="REFUND_APPROVED",
    funding=None,
):
    """执行退款。

    funding 默认由商户待结算承担；仲裁判定为平台责任时传 "PLATFORM"，
    费用从平台佣金收入支出，商户结算项保持原金额并解冻。
    """
    funding = funding or Funding.MERCHANT
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        remaining = order.paid_amount - order.refunded_amount
        if amount <= 0 or amount > remaining:
            raise ApiError("REFUND_AMOUNT_EXCEEDED", "退款金额超过可退金额", 409, {"refundable_amount": remaining})
        if order.order_type == Order.Type.COUPON and order.status in (
            Order.Status.PENDING_FULFILL,
            Order.Status.AFTER_SALE,
        ):
            # 卡券尚未履约完成：仅支持全额退款，避免部分退款后资金悬空与剩余码失效
            if amount < remaining:
                raise ApiError(
                    "REFUND_AMOUNT_EXCEEDED",
                    "卡券未核销完成前仅支持全额退款",
                    409,
                    {"refundable_amount": remaining},
                )

        payment = (
            PaymentOrder.objects.filter(
                order=order,
                status__in=[
                    PaymentOrder.Status.PAID,
                    PaymentOrder.Status.PARTIAL_REFUNDED,
                    PaymentOrder.Status.REFUNDING,
                ],
            )
            .order_by("-created_at")
            .first()
        )
        if payment is None:
            raise ApiError("PAYMENT_NOT_FOUND", "支付单不存在", 404)

        item = SettlementItem.objects.select_for_update().filter(order=order).first()

        was_pending_accept = order.status == Order.Status.PENDING_ACCEPT
        if was_pending_accept:
            transit_order(
                order.id,
                reject_event or "MERCHANT_REJECT",
                operator_type="MERCHANT",
                reason=reason,
            )
        elif order.status == Order.Status.AFTER_SALE:
            transit_order(order.id, approve_event, operator_type="SYSTEM", reason=reason)
        elif order.status == Order.Status.COMPLETED and after_sale is not None:
            transit_order(order.id, "APPLY_AFTER_SALE", operator_type="USER")
            transit_order(order.id, "REFUND_APPROVED", operator_type="SYSTEM", reason=reason)
        elif order.status != Order.Status.REFUNDING:
            raise ApiError("ORDER_STATE_CONFLICT", "当前状态不允许退款", 409)

        if item and item.status == SettlementItem.Status.FROZEN:
            lock_amount = order.paid_amount - order.refunded_amount
            if lock_amount > 0:
                post_transaction(
                    biz_type="FREEZE",
                    event_type="AFTER_SALE_UNFREEZE",
                    idempotency_key=f"after_sale_unfreeze:{after_sale.id if after_sale else order.id}",
                    entries=[
                        {
                            "account_type": AccountType.MERCHANT_FROZEN,
                            "account_id": order.merchant_id,
                            "direction": Direction.DEBIT,
                            "amount": lock_amount,
                        },
                        {
                            "account_type": AccountType.MERCHANT_PENDING,
                            "account_id": order.merchant_id,
                            "direction": Direction.CREDIT,
                            "amount": lock_amount,
                        },
                    ],
                )
            item.status = SettlementItem.Status.PENDING
            item.save(update_fields=["status", "updated_at"])

        split = apply_refund(
            order,
            amount,
            order_item=after_sale.order_item if after_sale is not None else None,
            funding=funding,
        )

        refund = RefundOrder.objects.create(
            refund_no=default_refund_no(),
            order=order,
            payment=payment,
            after_sale=after_sale,
            amount=amount,
            reason=reason,
            status=RefundOrder.Status.PROCESSING,
        )
        transaction_id = refund_payment(payment, refund.refund_no, amount)
        if item and item.status == SettlementItem.Status.SETTLED and funding != Funding.PLATFORM:
            # 已结算订单：从可提现扣减，平台佣金与商家应得均已按行冲回
            platform_share = split["platform_refund"]
            merchant_share = split["merchant_refund"]
            entries = []
            if merchant_share > 0:
                entries.append(
                    {
                        "account_type": AccountType.MERCHANT_AVAILABLE,
                        "account_id": order.merchant_id,
                        "direction": Direction.DEBIT,
                        "amount": merchant_share,
                    }
                )
            if platform_share > 0:
                entries.append(
                    {
                        "account_type": AccountType.PLATFORM_COMMISSION_REVENUE,
                        "account_id": 0,
                        "direction": Direction.DEBIT,
                        "amount": platform_share,
                    }
                )
            entries.append(
                {
                    "account_type": AccountType.PLATFORM_CASH,
                    "account_id": 0,
                    "direction": Direction.CREDIT,
                    "amount": amount,
                }
            )
        else:
            debit_account = (
                AccountType.PLATFORM_COMMISSION_REVENUE if funding == Funding.PLATFORM else AccountType.MERCHANT_PENDING
            )
            entries = [
                {
                    "account_type": debit_account,
                    "account_id": 0 if funding == Funding.PLATFORM else order.merchant_id,
                    "direction": Direction.DEBIT,
                    "amount": amount,
                },
                {
                    "account_type": AccountType.PLATFORM_CASH,
                    "account_id": 0,
                    "direction": Direction.CREDIT,
                    "amount": amount,
                },
            ]
        post_transaction(
            biz_type="REFUND",
            biz_id=refund.id,
            event_type="REFUND_SUCCESS",
            idempotency_key=f"refund:{refund.refund_no}",
            entries=entries,
        )
        refund.status = RefundOrder.Status.SUCCESS
        refund.transaction_id = transaction_id
        refund.refunded_at = timezone.now()
        refund.save(update_fields=["status", "transaction_id", "refunded_at", "updated_at"])

        if item and funding != Funding.PLATFORM:
            item.refund_amount += amount
            item.commission_amount -= split["platform_refund"]
            item.net_amount -= split["merchant_refund"]
            update_fields = ["refund_amount", "commission_amount", "net_amount", "updated_at"]
            if item.status != SettlementItem.Status.SETTLED:
                item.status = (
                    SettlementItem.Status.CANCELLED
                    if order.refunded_amount >= order.paid_amount
                    else SettlementItem.Status.PENDING
                )
                update_fields.append("status")
            item.save(update_fields=update_fields)

        if order.refunded_amount >= payment.amount:
            payment.status = PaymentOrder.Status.REFUNDED
        else:
            payment.status = PaymentOrder.Status.PARTIAL_REFUNDED
        payment.save(update_fields=["status", "updated_at"])

        if after_sale is not None:
            after_sale.approved_amount = amount
            after_sale.status = after_sale.Status.COMPLETED
            after_sale.closed_at = timezone.now()
            after_sale.save(update_fields=["approved_amount", "status", "closed_at", "updated_at"])

        if was_pending_accept:
            restore_order_resources(order)

        full_refund = order.refunded_amount >= order.paid_amount
        transit_order(
            order.id,
            "REFUND_SUCCESS_FULL" if full_refund else "REFUND_SUCCESS_PARTIAL",
            operator_type="SYSTEM",
        )
        if full_refund:
            from apps.coupons.services import release_user_coupon_by_order

            release_user_coupon_by_order(order.id)
            if order.order_type == Order.Type.COUPON:
                from apps.fulfillment.models import VerifyCode

                VerifyCode.objects.filter(order=order, status=VerifyCode.Status.ACTIVE).update(
                    status=VerifyCode.Status.INVALID
                )
    return refund
