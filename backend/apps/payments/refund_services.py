"""退款服务：未结算订单的退款、记账与订单状态联动。

已结算订单的退款（可提现/佣金冲回）留在 M3。
"""

from decimal import ROUND_HALF_UP, Decimal
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
        settled_commission_reversal = 0
        if item and item.status == SettlementItem.Status.SETTLED and funding != Funding.PLATFORM:
            # 已结算订单：从可提现扣减，佣金按退款金额等比冲回
            settled_commission_reversal = min(
                int((Decimal(amount) * Decimal(item.commission_rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
                item.commission_amount,
            )
            merchant_share = amount - settled_commission_reversal
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
            if settled_commission_reversal > 0:
                entries.append(
                    {
                        "account_type": AccountType.PLATFORM_COMMISSION_REVENUE,
                        "account_id": 0,
                        "direction": Direction.DEBIT,
                        "amount": settled_commission_reversal,
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

        order.refunded_amount += amount
        order.save(update_fields=["refunded_amount", "updated_at"])

        if item and funding != Funding.PLATFORM:
            if item.status == SettlementItem.Status.SETTLED:
                item.refund_amount += amount
                item.commission_amount -= settled_commission_reversal
                item.net_amount -= amount - settled_commission_reversal
                item.save(update_fields=["refund_amount", "commission_amount", "net_amount", "updated_at"])
            else:
                item.refund_amount += amount
                item.net_amount = item.product_amount + item.delivery_fee - item.commission_amount - item.refund_amount
                if order.refunded_amount >= order.paid_amount:
                    item.status = SettlementItem.Status.CANCELLED
                else:
                    item.status = SettlementItem.Status.PENDING
                item.save(update_fields=["refund_amount", "net_amount", "status", "updated_at"])

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
    return refund
