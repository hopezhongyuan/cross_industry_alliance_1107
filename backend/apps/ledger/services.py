"""记账服务：唯一写入口，负责校验借贷平衡、幂等与余额快照。"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional

from django.db import transaction
from django.db.models import F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.common.api import ApiError
from apps.governance.services import log_operation, require_platform_admin
from apps.ledger.constants import (
    DEBIT_NORMAL_ACCOUNTS,
    MERCHANT_BALANCE_FIELD,
    NON_NEGATIVE_FIELDS,
    AccountType,
    Direction,
)
from apps.ledger.models import (
    LedgerEntry,
    LedgerTransaction,
    MerchantAccount,
    SettlementBatch,
    SettlementItem,
    WithdrawalOrder,
)


class LedgerError(Exception):
    """记账业务错误。"""


class InvalidEntry(LedgerError):
    pass


class UnbalancedTransaction(LedgerError):
    pass


class NegativeBalance(LedgerError):
    pass


def ensure_account(merchant_id: int) -> MerchantAccount:
    account, _ = MerchantAccount.objects.get_or_create(merchant_id=merchant_id)
    return account


def _validate(entries: Iterable[dict]) -> int:
    total_debit = 0
    total_credit = 0
    valid_types = set(AccountType.values)
    for entry in entries:
        account_type = entry.get("account_type")
        direction = entry.get("direction")
        amount = entry.get("amount")
        account_id = entry.get("account_id", 0)
        if account_type not in valid_types:
            raise InvalidEntry(f"未知科目：{account_type}")
        if direction not in (Direction.DEBIT, Direction.CREDIT):
            raise InvalidEntry(f"未知借贷方向：{direction}")
        if not isinstance(amount, int) or amount <= 0:
            raise InvalidEntry("分录金额必须为正整数（分）")
        if not isinstance(account_id, int) or account_id < 0:
            raise InvalidEntry("账户 ID 非法")
        if direction == Direction.DEBIT:
            total_debit += amount
        else:
            total_credit += amount
    if total_debit != total_credit:
        raise UnbalancedTransaction(f"借贷不平：借方 {total_debit} / 贷方 {total_credit}")
    return total_debit


def _signed_delta(account_type: str, direction: str, amount: int) -> int:
    debit_normal = account_type in DEBIT_NORMAL_ACCOUNTS
    if (debit_normal and direction == Direction.DEBIT) or (not debit_normal and direction == Direction.CREDIT):
        return amount
    return -amount


def _platform_balance(account_type: str, account_id: int) -> int:
    filters = {"account_type": account_type, "account_id": account_id}
    debit = LedgerEntry.objects.filter(**filters, direction=Direction.DEBIT).aggregate(v=Sum("amount"))["v"] or 0
    credit = LedgerEntry.objects.filter(**filters, direction=Direction.CREDIT).aggregate(v=Sum("amount"))["v"] or 0
    return debit - credit if account_type in DEBIT_NORMAL_ACCOUNTS else credit - debit


def _post_entry(txn: LedgerTransaction, entry: dict) -> None:
    account_type = entry["account_type"]
    account_id = entry.get("account_id", 0)
    direction = entry["direction"]
    amount = entry["amount"]
    balance_field = MERCHANT_BALANCE_FIELD.get(account_type)

    if balance_field:
        ensure_account(account_id)
        account = MerchantAccount.objects.select_for_update().get(merchant_id=account_id)
        delta = _signed_delta(account_type, direction, amount)
        new_balance = getattr(account, balance_field) + delta
        if balance_field in NON_NEGATIVE_FIELDS and new_balance < 0:
            raise NegativeBalance(f"{account_type} 余额不足：当前 {getattr(account, balance_field)}，变动 {delta}")
        setattr(account, balance_field, new_balance)
        account.version += 1
        account.save(update_fields=[balance_field, "version", "updated_at"])
        balance_after = new_balance
    else:
        delta = _signed_delta(account_type, direction, amount)
        balance_after = _platform_balance(account_type, account_id) + delta

    LedgerEntry.objects.create(
        txn=txn,
        account_type=account_type,
        account_id=account_id,
        direction=direction,
        amount=amount,
        balance_after=balance_after,
        remark=entry.get("remark", ""),
    )


def post_transaction(
    *,
    biz_type: str,
    event_type: str,
    idempotency_key: str,
    entries: Iterable[dict],
    biz_id: Optional[int] = None,
    total_amount: Optional[int] = None,
    remark: str = "",
) -> LedgerTransaction:
    """写一笔平衡的记账事务。

    entries 元素：{"account_type", "account_id", "direction", "amount", "remark"}。
    幂等键重复时直接返回原事务，不重复记账、不改余额。
    """
    payload = list(entries)
    debit_total = _validate(payload)
    amount_for_txn = total_amount if total_amount is not None else debit_total
    if amount_for_txn != debit_total:
        raise UnbalancedTransaction("total_amount 必须等于借方合计")

    with transaction.atomic():
        txn, created = LedgerTransaction.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "biz_type": biz_type,
                "biz_id": biz_id,
                "event_type": event_type,
                "total_amount": amount_for_txn,
                "remark": remark,
            },
        )
        if not created:
            return txn
        for entry in payload:
            _post_entry(txn, entry)
    return txn


def create_settlement_item(order) -> SettlementItem:
    """订单完成时生成结算项：due_at = completed_at + 商户结算周期 N 天。"""
    from apps.orders.models import Order

    if order.status != Order.Status.COMPLETED or order.completed_at is None:
        raise LedgerError("只有已完成订单才能生成结算项")

    cycle_days = order.merchant.settlement_cycle_days
    net_amount = order.product_amount + order.delivery_fee - order.commission_amount - order.refunded_amount
    item, created = SettlementItem.objects.get_or_create(
        order=order,
        defaults={
            "merchant": order.merchant,
            "order_completed_at": order.completed_at,
            "due_at": order.completed_at + timedelta(days=cycle_days),
            "product_amount": order.product_amount,
            "delivery_fee": order.delivery_fee,
            "commission_rate": order.commission_rate,
            "commission_amount": order.commission_amount,
            "refund_amount": order.refunded_amount,
            "net_amount": net_amount,
        },
    )
    return item


def effective_commission(item: SettlementItem) -> int:
    """按退款后的结算基数重算佣金；佣金按退款金额等比冲回。"""
    gross = item.product_amount + item.delivery_fee - item.refund_amount
    if gross <= 0:
        return 0
    commission = int((Decimal(gross) * Decimal(item.commission_rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return max(0, min(commission, gross))


def create_settlement_batch(period_end=None) -> Optional[SettlementBatch]:
    """扫描到期未冻结的结算项，生成待发布批次。"""
    now = timezone.now()
    period_end = period_end or timezone.localdate()
    with transaction.atomic():
        items = list(
            SettlementItem.objects.select_for_update()
            .filter(status=SettlementItem.Status.PENDING, batch__isnull=True, due_at__lte=now)
            .order_by("due_at", "id")
        )
        if not items:
            return None
        period_start = min(item.due_at.date() for item in items)
        total_amount = 0
        commission_amount = 0
        net_amount = 0
        for item in items:
            gross = item.product_amount + item.delivery_fee - item.refund_amount
            commission = effective_commission(item)
            total_amount += gross
            commission_amount += commission
            net_amount += gross - commission
        batch = SettlementBatch.objects.create(
            period_start=period_start,
            period_end=period_end,
            total_amount=total_amount,
            commission_amount=commission_amount,
            net_amount=net_amount,
        )
        SettlementItem.objects.filter(pk__in=[item.pk for item in items]).update(batch=batch, updated_at=now)
    return batch


def publish_settlement_batch(batch_id: int, admin_user, request=None) -> SettlementBatch:
    """发布结算批次：待结算转可提现，佣金计入平台收入；重复发布幂等。"""
    require_platform_admin(admin_user)
    now = timezone.now()
    with transaction.atomic():
        batch = SettlementBatch.objects.select_for_update().filter(pk=batch_id).first()
        if batch is None:
            raise ApiError("NOT_FOUND", "结算批次不存在", 404)
        if batch.status == SettlementBatch.Status.PUBLISHED:
            return batch
        if batch.status == SettlementBatch.Status.CLOSED:
            raise ApiError("SETTLEMENT_BATCH_CLOSED", "结算批次已关闭", 409)

        items = list(
            SettlementItem.objects.select_for_update()
            .filter(batch=batch, status=SettlementItem.Status.PENDING)
            .select_related("order")
            .order_by("due_at", "id")
        )
        if not items:
            raise ApiError("SETTLEMENT_NOT_DUE", "批次内没有可结算项", 409)

        total_amount = 0
        commission_amount = 0
        net_amount = 0
        settled_ids = []
        for item in items:
            gross = item.product_amount + item.delivery_fee - item.refund_amount
            if gross <= 0:
                item.status = SettlementItem.Status.CANCELLED
                item.batch = None
                item.save(update_fields=["status", "batch", "updated_at"])
                continue
            commission = effective_commission(item)
            net = gross - commission
            entries = [
                {
                    "account_type": AccountType.MERCHANT_PENDING,
                    "account_id": item.merchant_id,
                    "direction": Direction.DEBIT,
                    "amount": gross,
                },
                {
                    "account_type": AccountType.MERCHANT_AVAILABLE,
                    "account_id": item.merchant_id,
                    "direction": Direction.CREDIT,
                    "amount": net,
                },
            ]
            if commission > 0:
                entries.append(
                    {
                        "account_type": AccountType.PLATFORM_COMMISSION_REVENUE,
                        "account_id": 0,
                        "direction": Direction.CREDIT,
                        "amount": commission,
                    }
                )
            post_transaction(
                biz_type="SETTLEMENT",
                biz_id=item.id,
                event_type="SETTLEMENT_PUBLISHED",
                idempotency_key=f"settlement:{batch.batch_no}:{item.id}",
                entries=entries,
            )
            item.commission_amount = commission
            item.net_amount = net
            item.status = SettlementItem.Status.SETTLED
            item.settled_at = now
            item.save(update_fields=["commission_amount", "net_amount", "status", "settled_at", "updated_at"])
            total_amount += gross
            commission_amount += commission
            net_amount += net
            settled_ids.append(item.pk)

        # 冻结或其他状态未结算的项退回待批次，等解冻后重新扫描
        SettlementItem.objects.filter(batch=batch).exclude(pk__in=settled_ids).exclude(
            status=SettlementItem.Status.CANCELLED
        ).update(batch=None, updated_at=now)

        batch.total_amount = total_amount
        batch.commission_amount = commission_amount
        batch.net_amount = net_amount
        batch.status = SettlementBatch.Status.PUBLISHED
        batch.published_at = now
        batch.published_by_id = admin_user.id
        batch.published_by_name = getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", "") or ""
        batch.save(
            update_fields=[
                "total_amount",
                "commission_amount",
                "net_amount",
                "status",
                "published_at",
                "published_by_id",
                "published_by_name",
                "updated_at",
            ]
        )
        log_operation(
            operator=admin_user,
            action="SETTLEMENT_PUBLISH",
            biz_type="SETTLEMENT_BATCH",
            biz_id=batch.id,
            after={"batch_no": batch.batch_no, "items": len(settled_ids)},
            request=request,
        )
    return batch


def request_withdrawal(user, amount: int, bank_account_id=None, idempotency_key="", request=None) -> WithdrawalOrder:
    """商户申请提现：可提现转提现中。"""
    from apps.merchants.services import get_active_staff_merchant

    merchant = get_active_staff_merchant(user)
    with transaction.atomic():
        if idempotency_key:
            existing = WithdrawalOrder.objects.filter(idempotency_key=idempotency_key).first()
            if existing is not None:
                if existing.merchant_id != merchant.id:
                    raise ApiError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他提现申请", 409)
                return existing
        ensure_account(merchant.id)
        account = MerchantAccount.objects.select_for_update().get(merchant=merchant)
        if account.available_balance < amount:
            raise ApiError(
                "WITHDRAW_BALANCE_NOT_ENOUGH",
                "可提现余额不足",
                409,
                {"available_balance": account.available_balance},
            )
        fee = 0  # TBD：提现手续费规则未确认，P0 按 0 处理
        withdrawal = WithdrawalOrder.objects.create(
            merchant=merchant,
            account=account,
            amount=amount,
            fee=fee,
            net_amount=amount - fee,
            idempotency_key=idempotency_key or None,
            bank_snapshot_json=merchant.bank_info or {},
            status=WithdrawalOrder.Status.REQUESTED,
            requested_at=timezone.now(),
        )
        post_transaction(
            biz_type="WITHDRAWAL",
            biz_id=withdrawal.id,
            event_type="WITHDRAWAL_REQUESTED",
            idempotency_key=f"withdrawal:{withdrawal.withdrawal_no}:request",
            entries=[
                {
                    "account_type": AccountType.MERCHANT_AVAILABLE,
                    "account_id": merchant.id,
                    "direction": Direction.DEBIT,
                    "amount": amount,
                },
                {
                    "account_type": AccountType.MERCHANT_WITHDRAWING,
                    "account_id": merchant.id,
                    "direction": Direction.CREDIT,
                    "amount": amount,
                },
            ],
        )
        log_operation(
            operator=user,
            action="WITHDRAWAL_REQUEST",
            biz_type="WITHDRAWAL",
            biz_id=withdrawal.id,
            after={"withdrawal_no": withdrawal.withdrawal_no, "amount": amount},
            request=request,
        )
    return withdrawal


def payout_withdrawal(
    admin_user,
    withdrawal_id: int,
    voucher_no: str,
    voucher_url: str,
    paid_at,
    request=None,
) -> WithdrawalOrder:
    """确认线下打款：提现中转平台现金，回填回单。"""
    require_platform_admin(admin_user)
    with transaction.atomic():
        withdrawal = WithdrawalOrder.objects.select_for_update().filter(pk=withdrawal_id).first()
        if withdrawal is None:
            raise ApiError("NOT_FOUND", "提现单不存在", 404)
        if withdrawal.status == WithdrawalOrder.Status.PAID:
            return withdrawal
        if withdrawal.status not in (
            WithdrawalOrder.Status.REQUESTED,
            WithdrawalOrder.Status.APPROVED,
            WithdrawalOrder.Status.PAYING,
        ):
            raise ApiError("WITHDRAWAL_STATE_CONFLICT", "当前提现状态不允许打款", 409)

        post_transaction(
            biz_type="WITHDRAWAL",
            biz_id=withdrawal.id,
            event_type="WITHDRAWAL_PAID",
            idempotency_key=f"withdrawal:{withdrawal.withdrawal_no}:payout",
            entries=[
                {
                    "account_type": AccountType.MERCHANT_WITHDRAWING,
                    "account_id": withdrawal.merchant_id,
                    "direction": Direction.DEBIT,
                    "amount": withdrawal.amount,
                },
                {
                    "account_type": AccountType.PLATFORM_CASH,
                    "account_id": 0,
                    "direction": Direction.CREDIT,
                    "amount": withdrawal.amount,
                },
            ],
        )
        withdrawal.status = WithdrawalOrder.Status.PAID
        withdrawal.paid_at = paid_at
        withdrawal.voucher_no = voucher_no
        withdrawal.voucher_url = voucher_url
        withdrawal.reviewed_by_id = admin_user.id
        withdrawal.reviewed_by_name = getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", "") or ""
        withdrawal.reviewed_at = timezone.now()
        withdrawal.save(
            update_fields=[
                "status",
                "paid_at",
                "voucher_no",
                "voucher_url",
                "reviewed_by_id",
                "reviewed_by_name",
                "reviewed_at",
                "updated_at",
            ]
        )
        log_operation(
            operator=admin_user,
            action="WITHDRAWAL_PAYOUT",
            biz_type="WITHDRAWAL",
            biz_id=withdrawal.id,
            after={"withdrawal_no": withdrawal.withdrawal_no, "voucher_no": voucher_no},
            request=request,
        )
    return withdrawal


def reject_withdrawal(admin_user, withdrawal_id: int, reason: str, request=None) -> WithdrawalOrder:
    """驳回提现：提现中退回可提现。"""
    require_platform_admin(admin_user)
    with transaction.atomic():
        withdrawal = WithdrawalOrder.objects.select_for_update().filter(pk=withdrawal_id).first()
        if withdrawal is None:
            raise ApiError("NOT_FOUND", "提现单不存在", 404)
        if withdrawal.status not in (
            WithdrawalOrder.Status.REQUESTED,
            WithdrawalOrder.Status.APPROVED,
            WithdrawalOrder.Status.PAYING,
        ):
            raise ApiError("WITHDRAWAL_STATE_CONFLICT", "当前提现状态不允许驳回", 409)

        post_transaction(
            biz_type="WITHDRAWAL",
            biz_id=withdrawal.id,
            event_type="WITHDRAWAL_REJECTED",
            idempotency_key=f"withdrawal:{withdrawal.withdrawal_no}:reject",
            entries=[
                {
                    "account_type": AccountType.MERCHANT_WITHDRAWING,
                    "account_id": withdrawal.merchant_id,
                    "direction": Direction.DEBIT,
                    "amount": withdrawal.amount,
                },
                {
                    "account_type": AccountType.MERCHANT_AVAILABLE,
                    "account_id": withdrawal.merchant_id,
                    "direction": Direction.CREDIT,
                    "amount": withdrawal.amount,
                },
            ],
        )
        withdrawal.status = WithdrawalOrder.Status.REJECTED
        withdrawal.fail_reason = reason
        withdrawal.reviewed_by_id = admin_user.id
        withdrawal.reviewed_by_name = getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", "") or ""
        withdrawal.reviewed_at = timezone.now()
        withdrawal.save(
            update_fields=[
                "status",
                "fail_reason",
                "reviewed_by_id",
                "reviewed_by_name",
                "reviewed_at",
                "updated_at",
            ]
        )
        log_operation(
            operator=admin_user,
            action="WITHDRAWAL_REJECT",
            biz_type="WITHDRAWAL",
            biz_id=withdrawal.id,
            reason=reason,
            request=request,
        )
    return withdrawal


def set_order_settlement_freeze(
    admin_user, order_id: int, action: str, reason: str, idempotency_key: str, request=None
):
    """平台冻结/解冻结算项：只动资金，不影响履约。"""
    require_platform_admin(admin_user)
    with transaction.atomic():
        item = SettlementItem.objects.select_for_update().filter(order_id=order_id).select_related("order").first()
        if item is None:
            raise ApiError("NOT_FOUND", "结算项不存在", 404)
        order = item.order
        lock_amount = order.paid_amount - order.refunded_amount
        if action == "FREEZE":
            if item.status == SettlementItem.Status.FROZEN:
                return item
            if item.status != SettlementItem.Status.PENDING:
                raise ApiError("SETTLEMENT_STATE_CONFLICT", "当前结算项状态不允许冻结", 409)
            if lock_amount <= 0:
                raise ApiError("SETTLEMENT_STATE_CONFLICT", "没有可冻结金额", 409)
            entries = [
                {
                    "account_type": AccountType.MERCHANT_PENDING,
                    "account_id": item.merchant_id,
                    "direction": Direction.DEBIT,
                    "amount": lock_amount,
                },
                {
                    "account_type": AccountType.MERCHANT_FROZEN,
                    "account_id": item.merchant_id,
                    "direction": Direction.CREDIT,
                    "amount": lock_amount,
                },
            ]
            item.status = SettlementItem.Status.FROZEN
        else:
            if item.status == SettlementItem.Status.PENDING:
                return item
            if item.status != SettlementItem.Status.FROZEN:
                raise ApiError("SETTLEMENT_STATE_CONFLICT", "当前结算项状态不允许解冻", 409)
            if lock_amount <= 0:
                raise ApiError("SETTLEMENT_STATE_CONFLICT", "没有可解冻金额", 409)
            entries = [
                {
                    "account_type": AccountType.MERCHANT_FROZEN,
                    "account_id": item.merchant_id,
                    "direction": Direction.DEBIT,
                    "amount": lock_amount,
                },
                {
                    "account_type": AccountType.MERCHANT_PENDING,
                    "account_id": item.merchant_id,
                    "direction": Direction.CREDIT,
                    "amount": lock_amount,
                },
            ]
            item.status = SettlementItem.Status.PENDING
        post_transaction(
            biz_type="FREEZE",
            biz_id=item.id,
            event_type=f"ADMIN_{action}",
            idempotency_key=f"order_freeze:{order_id}:{idempotency_key}",
            entries=entries,
        )
        item.save(update_fields=["status", "updated_at"])
        log_operation(
            operator=admin_user,
            action=f"SETTLEMENT_{action}",
            biz_type="ORDER",
            biz_id=order_id,
            reason=reason,
            request=request,
        )
    return item


def _ledger_imbalance() -> tuple:
    rows = list(
        LedgerTransaction.objects.annotate(
            debit=Coalesce(Sum("entries__amount", filter=Q(entries__direction=Direction.DEBIT)), Value(0)),
            credit=Coalesce(Sum("entries__amount", filter=Q(entries__direction=Direction.CREDIT)), Value(0)),
        )
        .exclude(debit=F("credit"))
        .values_list("debit", "credit")
    )
    return len(rows), sum(abs(debit - credit) for debit, credit in rows)


def _account_drift() -> int:
    totals = {}
    rows = (
        LedgerEntry.objects.filter(account_type__in=MERCHANT_BALANCE_FIELD, account_id__gt=0)
        .values("account_type", "account_id", "direction")
        .annotate(total=Sum("amount"))
    )
    for row in rows:
        account_type = row["account_type"]
        direction = row["direction"]
        amount = row["total"] or 0
        increase = (
            direction == Direction.DEBIT if account_type in DEBIT_NORMAL_ACCOUNTS else direction == Direction.CREDIT
        )
        totals[(account_type, row["account_id"])] = totals.get((account_type, row["account_id"]), 0) + (
            amount if increase else -amount
        )
    diffs = 0
    for account in MerchantAccount.objects.all():
        for account_type, field in MERCHANT_BALANCE_FIELD.items():
            expected = totals.get((account_type, account.merchant_id), 0)
            if expected != getattr(account, field):
                diffs += 1
    return diffs


def _settlement_drift() -> int:
    return (
        SettlementItem.objects.filter(Q(status=SettlementItem.Status.SETTLED, batch__isnull=True)).count()
        + SettlementItem.objects.filter(
            Q(status=SettlementItem.Status.SETTLED, batch__isnull=False)
            & ~Q(batch__status=SettlementBatch.Status.PUBLISHED)
        ).count()
        + SettlementItem.objects.filter(
            Q(status=SettlementItem.Status.PENDING, batch__status=SettlementBatch.Status.PUBLISHED)
        ).count()
    )


def _refund_drift() -> int:
    from apps.orders.models import Order

    rows = (
        Order.objects.annotate(
            refund_sum=Coalesce(Sum("refunds__amount", filter=Q(refunds__status="SUCCESS")), Value(0))
        )
        .exclude(refunded_amount=F("refund_sum"))
        .count()
    )
    return rows


def reconciliation_report(date=None) -> dict:
    """对账结果：记账平衡、账户快照、结算一致性与退款一致。"""
    date = date or timezone.localdate()
    balance_count, balance_amount = _ledger_imbalance()
    account_diffs = _account_drift()
    settlement_diffs = _settlement_drift()
    refund_diffs = _refund_drift()
    checks = [
        {
            "name": "LEDGER_BALANCE",
            "status": "OK" if balance_count == 0 else "DIFF",
            "diff_count": balance_count,
            "diff_amount": balance_amount,
        },
        {
            "name": "ACCOUNT_SNAPSHOT",
            "status": "OK" if account_diffs == 0 else "DIFF",
            "diff_count": account_diffs,
            "diff_amount": 0,
        },
        {
            "name": "SETTLEMENT_CONSISTENCY",
            "status": "OK" if settlement_diffs == 0 else "DIFF",
            "diff_count": settlement_diffs,
            "diff_amount": 0,
        },
        {
            "name": "REFUND_CONSISTENCY",
            "status": "OK" if refund_diffs == 0 else "DIFF",
            "diff_count": refund_diffs,
            "diff_amount": 0,
        },
    ]
    return {
        "date": date.isoformat(),
        "checks": checks,
        "unresolved_count": sum(1 for check in checks if check["status"] == "DIFF"),
    }
