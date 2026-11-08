"""退款服务：未结算订单的退款、记账与订单状态联动。

已结算订单的退款（可提现/佣金冲回）留在 M3。
"""

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


def refund_order(order_id: int, amount: int, reason: str, after_sale=None, reject_event=None):
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
        if item and item.status == SettlementItem.Status.SETTLED:
            raise ApiError("SETTLEMENT_ALREADY_SETTLED", "已结算订单退款请在 M3 处理", 409)

        was_pending_accept = order.status == Order.Status.PENDING_ACCEPT
        if was_pending_accept:
            transit_order(
                order.id,
                reject_event or "MERCHANT_REJECT",
                operator_type="MERCHANT",
                reason=reason,
            )
        elif order.status == Order.Status.AFTER_SALE:
            transit_order(order.id, "REFUND_APPROVED", operator_type="SYSTEM", reason=reason)
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
        post_transaction(
            biz_type="REFUND",
            biz_id=refund.id,
            event_type="REFUND_SUCCESS",
            idempotency_key=f"refund:{refund.refund_no}",
            entries=[
                {
                    "account_type": AccountType.MERCHANT_PENDING,
                    "account_id": order.merchant_id,
                    "direction": Direction.DEBIT,
                    "amount": amount,
                },
                {
                    "account_type": AccountType.PLATFORM_CASH,
                    "account_id": 0,
                    "direction": Direction.CREDIT,
                    "amount": amount,
                },
            ],
        )
        refund.status = RefundOrder.Status.SUCCESS
        refund.transaction_id = transaction_id
        refund.refunded_at = timezone.now()
        refund.save(update_fields=["status", "transaction_id", "refunded_at", "updated_at"])

        order.refunded_amount += amount
        order.save(update_fields=["refunded_amount", "updated_at"])

        if item:
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
