"""售后申请、商户处理、超时转仲裁与结算冻结。"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError
from apps.governance.services import require_platform_admin
from apps.ledger.constants import AccountType, Direction
from apps.ledger.models import SettlementItem
from apps.ledger.services import post_transaction
from apps.merchants.services import get_active_staff_merchant
from apps.orders.models import Order
from apps.orders.services import transit_order
from apps.payments.refund_services import Funding, refund_order

from .models import AfterSale, ArbitrationCase

ACTIVE_STATUSES = {
    AfterSale.Status.APPLIED,
    AfterSale.Status.MERCHANT_PROCESSING,
    AfterSale.Status.MERCHANT_AGREED,
    AfterSale.Status.MERCHANT_REJECTED,
    AfterSale.Status.ARBITRATING,
    AfterSale.Status.RESOLVED,
    AfterSale.Status.REFUNDING,
}


def apply_after_sale(
    user,
    order_id,
    type,
    reason_code,
    request_amount,
    description="",
    evidence=None,
    order_item_id=None,
):
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        if order.status != Order.Status.COMPLETED:
            raise ApiError("AFTER_SALE_NOT_ALLOWED", "当前订单状态不支持售后", 409)
        if AfterSale.objects.filter(order=order, status__in=ACTIVE_STATUSES).exists():
            raise ApiError("AFTER_SALE_ALREADY_EXISTS", "该订单已有进行中的售后", 409)

        remaining = order.paid_amount - order.refunded_amount
        if request_amount <= 0 or request_amount > remaining:
            raise ApiError("REFUND_AMOUNT_EXCEEDED", "申请金额超过可退金额", 409, {"refundable_amount": remaining})

        after_sale = AfterSale.objects.create(
            order=order,
            order_item_id=order_item_id,
            user=user,
            merchant=order.merchant,
            type=type,
            reason_code=reason_code,
            description=description,
            evidence_json=evidence or [],
            request_amount=request_amount,
            status=AfterSale.Status.APPLIED,
            deadline_at=timezone.now() + timedelta(hours=settings.AFTER_SALE_MERCHANT_DEADLINE_HOURS),
        )
        transit_order(order.id, "APPLY_AFTER_SALE", operator_type="USER", operator_id=user.id)

        item = SettlementItem.objects.select_for_update().filter(order=order).first()
        if item and item.status == SettlementItem.Status.PENDING:
            lock_amount = order.paid_amount - order.refunded_amount
            if lock_amount > 0:
                post_transaction(
                    biz_type="FREEZE",
                    biz_id=after_sale.id,
                    event_type="AFTER_SALE_FREEZE",
                    idempotency_key=f"after_sale_freeze:{after_sale.id}",
                    entries=[
                        {
                            "account_type": AccountType.MERCHANT_PENDING,
                            "account_id": order.merchant_id,
                            "direction": Direction.DEBIT,
                            "amount": lock_amount,
                        },
                        {
                            "account_type": AccountType.MERCHANT_FROZEN,
                            "account_id": order.merchant_id,
                            "direction": Direction.CREDIT,
                            "amount": lock_amount,
                        },
                    ],
                )
            item.status = SettlementItem.Status.FROZEN
            item.save(update_fields=["status", "updated_at"])
    return after_sale


def _unfreeze(order, after_sale):
    item = SettlementItem.objects.select_for_update().filter(order=order).first()
    if item is None or item.status != SettlementItem.Status.FROZEN:
        return
    lock_amount = order.paid_amount - order.refunded_amount
    if lock_amount > 0:
        post_transaction(
            biz_type="FREEZE",
            biz_id=after_sale.id,
            event_type="AFTER_SALE_UNFREEZE",
            idempotency_key=f"after_sale_unfreeze:{after_sale.id}",
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


def decide_after_sale(user, after_sale_id, decision, approved_amount=None, reason=""):
    merchant = get_active_staff_merchant(user)
    with transaction.atomic():
        after_sale = AfterSale.objects.select_for_update().filter(pk=after_sale_id, merchant=merchant).first()
        if after_sale is None:
            raise ApiError("NOT_FOUND", "售后单不存在", 404)
        if after_sale.status not in (AfterSale.Status.APPLIED, AfterSale.Status.MERCHANT_PROCESSING):
            raise ApiError("ORDER_STATE_CONFLICT", "当前售后状态不允许处理", 409)

        order = Order.objects.select_for_update().get(pk=after_sale.order_id)
        if decision == "AGREE":
            amount = approved_amount or after_sale.request_amount
            remaining = order.paid_amount - order.refunded_amount
            if amount <= 0 or amount > remaining:
                raise ApiError(
                    "REFUND_AMOUNT_EXCEEDED",
                    "批准金额超过可退金额",
                    409,
                    {"refundable_amount": remaining},
                )
            after_sale.status = AfterSale.Status.MERCHANT_AGREED
            after_sale.merchant_decision = AfterSale.MerchantDecision.AGREED
            after_sale.approved_amount = amount
            after_sale.merchant_reason = reason
            after_sale.save(
                update_fields=[
                    "status",
                    "merchant_decision",
                    "approved_amount",
                    "merchant_reason",
                    "updated_at",
                ]
            )
            refund_order(order.id, amount, reason or "商户同意售后", after_sale=after_sale)
        else:
            after_sale.status = AfterSale.Status.MERCHANT_REJECTED
            after_sale.merchant_decision = AfterSale.MerchantDecision.REJECTED
            after_sale.merchant_reason = reason
            after_sale.save(update_fields=["status", "merchant_decision", "merchant_reason", "updated_at"])
            transit_order(order.id, "MERCHANT_REJECT", operator_type="MERCHANT", operator_id=user.id, reason=reason)
            _unfreeze(order, after_sale)
    after_sale.refresh_from_db()
    return after_sale


def escalate_due_after_sales(now=None, limit=200) -> int:
    """扫描商户超时未处理的售后单，转平台仲裁；返回本次转仲裁数量。"""
    now = now or timezone.now()
    ids = list(
        AfterSale.objects.filter(
            status__in=(AfterSale.Status.APPLIED, AfterSale.Status.MERCHANT_PROCESSING),
            deadline_at__lte=now,
        ).values_list("id", flat=True)[:limit]
    )
    count = 0
    for pk in ids:
        with transaction.atomic():
            after_sale = AfterSale.objects.select_for_update().filter(pk=pk).first()
            if after_sale is None or after_sale.arbitration_case_id:
                continue
            if after_sale.status not in (AfterSale.Status.APPLIED, AfterSale.Status.MERCHANT_PROCESSING):
                continue
            case, _ = ArbitrationCase.objects.get_or_create(
                after_sale=after_sale,
                defaults={
                    "amount": after_sale.request_amount,
                    "status": ArbitrationCase.Status.PENDING,
                    "deadline_at": now + timedelta(hours=settings.ARBITRATION_SLA_HOURS),
                },
            )
            after_sale.status = AfterSale.Status.ARBITRATING
            after_sale.arbitration_case = case
            after_sale.save(update_fields=["status", "arbitration_case", "updated_at"])
            count += 1
    return count


def rule_arbitration(admin_user, case_id, liability, refund_amount=0, ruling=""):
    """平台裁定：记录责任方并执行退款。

    资金承担：商户/双方共担由商户待结算承担（双方分摊比例 TBD）；平台责任由平台佣金收入承担；
    用户责任不退款，解冻结算项并恢复订单为已完成。
    """
    require_platform_admin(admin_user)
    if liability == ArbitrationCase.Liability.USER and refund_amount > 0:
        raise ApiError("VALIDATION_ERROR", "用户责任不得同时执行退款", 422)

    with transaction.atomic():
        case = ArbitrationCase.objects.select_for_update().filter(pk=case_id).first()
        if case is None:
            raise ApiError("NOT_FOUND", "仲裁案不存在", 404)
        if case.status in (ArbitrationCase.Status.DECIDED, ArbitrationCase.Status.CLOSED):
            raise ApiError("ARBITRATION_STATE_CONFLICT", "仲裁案已裁定", 409)

        after_sale = AfterSale.objects.select_for_update().get(pk=case.after_sale_id)
        if after_sale.status != AfterSale.Status.ARBITRATING:
            raise ApiError("ARBITRATION_STATE_CONFLICT", "售后单不在仲裁中", 409)

        order = Order.objects.select_for_update().get(pk=after_sale.order_id)
        remaining = order.paid_amount - order.refunded_amount
        if refund_amount < 0 or refund_amount > remaining:
            raise ApiError(
                "REFUND_AMOUNT_EXCEEDED",
                "裁定退款金额超过可退金额",
                409,
                {"refundable_amount": remaining},
            )

        case.liability = liability
        case.ruling = ruling
        case.status = ArbitrationCase.Status.DECIDED
        case.decided_at = timezone.now()
        case.decided_by_id = admin_user.id
        case.decided_by_name = admin_user.nickname or admin_user.phone or str(admin_user.id)
        case.save(
            update_fields=[
                "liability",
                "ruling",
                "status",
                "decided_at",
                "decided_by_id",
                "decided_by_name",
                "updated_at",
            ]
        )

        if refund_amount > 0:
            funding = Funding.PLATFORM if liability == ArbitrationCase.Liability.PLATFORM else Funding.MERCHANT
            refund_order(
                order.id,
                refund_amount,
                reason=f"仲裁裁定：{ruling}",
                after_sale=after_sale,
                approve_event="ARBITRATION_REFUND",
                funding=funding,
            )
        else:
            after_sale.status = AfterSale.Status.CANCELLED
            after_sale.approved_amount = 0
            after_sale.closed_at = timezone.now()
            after_sale.save(update_fields=["status", "approved_amount", "closed_at", "updated_at"])
            transit_order(
                order.id,
                "ARBITRATION_REJECT",
                operator_type="SYSTEM",
                operator_id=admin_user.id,
                operator_name=case.decided_by_name,
                reason=ruling,
            )
            _unfreeze(order, after_sale)

    after_sale.refresh_from_db()
    return after_sale
