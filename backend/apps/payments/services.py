"""支付下单与回调处理。"""

from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError
from apps.governance.services import log_operation, require_platform_admin
from apps.ledger.constants import AccountType, Direction
from apps.ledger.services import post_transaction
from apps.orders.models import Order
from apps.orders.order_services import mark_order_paid
from apps.orders.services import transit_order

from .models import PaymentGroup, PaymentOrder, PlatformPaymentConfig
from .providers import create_prepay


def create_payment(user, order_id, channel, idempotency_key):
    with transaction.atomic():
        existing = PaymentOrder.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if existing.order_id != order_id or existing.user_id != user.id:
                raise ApiError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他支付请求", 409)
            return existing, {"mock": True} if existing.prepay_id else {}

        order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        if order.status != Order.Status.PENDING_PAYMENT:
            raise ApiError("ORDER_STATE_CONFLICT", "当前订单状态不允许支付", 409)
        if order.expire_at and timezone.now() > order.expire_at:
            raise ApiError("ORDER_EXPIRED", "订单已超时关闭", 409)

        payment = PaymentOrder.objects.filter(
            order=order, status__in=[PaymentOrder.Status.CREATED, PaymentOrder.Status.PAYING]
        ).first()
        if payment is None:
            if PaymentOrder.objects.filter(order=order, status=PaymentOrder.Status.PAID).exists():
                raise ApiError("ORDER_STATE_CONFLICT", "订单已支付", 409)
            payment = PaymentOrder.objects.create(
                order=order,
                user=user,
                channel=channel,
                amount=order.payable_amount,
                status=PaymentOrder.Status.CREATED,
                idempotency_key=idempotency_key,
                expire_at=order.expire_at,
            )

        prepay = create_prepay(payment)
        payment.prepay_id = prepay["prepay_id"]
        payment.status = PaymentOrder.Status.PAYING
        payment.save(update_fields=["prepay_id", "status", "updated_at"])
        return payment, prepay["pay_params"]


def process_payment_success(payment_no: str, transaction_id: str, amount: int) -> PaymentOrder:
    with transaction.atomic():
        payment = PaymentOrder.objects.select_for_update().filter(payment_no=payment_no).first()
        if payment is None:
            raise ApiError("PAYMENT_NOT_FOUND", "支付单不存在", 404)
        if amount != payment.amount:
            raise ApiError(
                "PAY_AMOUNT_MISMATCH",
                "回调金额与支付单不一致",
                409,
                {"expected_amount": payment.amount, "actual_amount": amount},
            )
        if payment.status == PaymentOrder.Status.PAID:
            if payment.transaction_id != transaction_id:
                raise ApiError("PAYMENT_TRANSACTION_CONFLICT", "交易号与已支付记录不一致", 409)
            return payment
        if payment.status in (PaymentOrder.Status.CLOSED, PaymentOrder.Status.REFUNDED):
            raise ApiError("ORDER_STATE_CONFLICT", "支付单已关闭或已退款", 409)

        order = Order.objects.filter(pk=payment.order_id).first()
        if order is None or order.status != Order.Status.PENDING_PAYMENT:
            raise ApiError("ORDER_STATE_CONFLICT", "订单状态不允许支付成功", 409)

        payment.status = PaymentOrder.Status.PAID
        payment.transaction_id = transaction_id
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "transaction_id", "paid_at", "updated_at"])

        order.paid_amount = payment.amount
        order.save(update_fields=["paid_amount", "updated_at"])

        transit_order(order.id, "PAY_SUCCESS", operator_type="SYSTEM")
        entries = [
            {
                "account_type": AccountType.PLATFORM_CASH,
                "account_id": 0,
                "direction": Direction.DEBIT,
                "amount": payment.amount,
            },
            {
                "account_type": AccountType.MERCHANT_PENDING,
                "account_id": order.merchant_id,
                "direction": Direction.CREDIT,
                "amount": payment.amount + order.platform_subsidy_amount,
            },
        ]
        if order.platform_subsidy_amount > 0:
            entries.append(
                {
                    "account_type": AccountType.PLATFORM_MARKETING_EXPENSE,
                    "account_id": 0,
                    "direction": Direction.DEBIT,
                    "amount": order.platform_subsidy_amount,
                }
            )
        post_transaction(
            biz_type="PAYMENT",
            biz_id=payment.id,
            event_type="PAY_SUCCESS",
            idempotency_key=f"payment:{payment.payment_no}",
            entries=entries,
        )
        mark_order_paid(order)

        # 消费返积分：与支付状态在同一事务，幂等键 points:order:{order_no}
        from apps.points.services import award_for_order_payment

        award_for_order_payment(
            user_id=order.user_id,
            order_no=order.order_no,
            paid_amount=payment.amount,
            order_id=order.id,
        )
    return payment


def create_group_payment(user, group_no, channel, idempotency_key):
    """为合单支付组发起支付（一笔支付覆盖组内所有订单）。"""
    with transaction.atomic():
        existing = PaymentGroup.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if existing.group_no != group_no or existing.user_id != user.id:
                raise ApiError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他支付请求", 409)
            return existing, {"mock": True} if existing.prepay_id else {}

        group = PaymentGroup.objects.select_for_update().filter(group_no=group_no, user=user).first()
        if group is None:
            raise ApiError("NOT_FOUND", "合单支付组不存在", 404)
        if group.status not in (PaymentGroup.Status.CREATED, PaymentGroup.Status.PAYING):
            raise ApiError("ORDER_STATE_CONFLICT", "合单支付组状态不允许支付", 409)

        orders = list(Order.objects.select_for_update().filter(payment_group=group).order_by("id"))
        if not orders:
            raise ApiError("ORDER_STATE_CONFLICT", "合单支付组没有关联订单", 409)
        for order in orders:
            if order.status != Order.Status.PENDING_PAYMENT:
                raise ApiError("ORDER_STATE_CONFLICT", f"订单 {order.order_no} 状态不允许支付", 409)
            if order.expire_at and timezone.now() > order.expire_at:
                raise ApiError("ORDER_EXPIRED", f"订单 {order.order_no} 已超时关闭", 409)

        total_amount = sum(order.payable_amount for order in orders)
        if group.amount != total_amount:
            group.amount = total_amount

        group.channel = channel
        group.idempotency_key = idempotency_key
        prepay = {"prepay_id": f"mock_{group.group_no}", "pay_params": {"mock": True}}
        group.prepay_id = prepay["prepay_id"]
        group.status = PaymentGroup.Status.PAYING
        group.save(update_fields=["channel", "idempotency_key", "prepay_id", "status", "amount", "updated_at"])
        return group, prepay["pay_params"]


def process_group_payment_success(group_no: str, transaction_id: str, amount: int) -> PaymentGroup:
    """合单支付回调成功：组内所有订单各自走状态机、记账、核销码、积分。"""
    from apps.points.services import award_for_order_payment

    with transaction.atomic():
        group = PaymentGroup.objects.select_for_update().filter(group_no=group_no).first()
        if group is None:
            raise ApiError("PAYMENT_NOT_FOUND", "合单支付组不存在", 404)
        if amount != group.amount:
            raise ApiError(
                "PAY_AMOUNT_MISMATCH",
                "回调金额与合单支付金额不一致",
                409,
                {"expected_amount": group.amount, "actual_amount": amount},
            )
        if group.status == PaymentGroup.Status.PAID:
            if group.transaction_id != transaction_id:
                raise ApiError("PAYMENT_TRANSACTION_CONFLICT", "交易号与已支付记录不一致", 409)
            return group
        if group.status in (PaymentGroup.Status.CLOSED,):
            raise ApiError("ORDER_STATE_CONFLICT", "合单支付组已关闭", 409)

        orders = list(Order.objects.select_for_update().filter(payment_group=group).order_by("id"))
        for order in orders:
            if order.status != Order.Status.PENDING_PAYMENT:
                raise ApiError("ORDER_STATE_CONFLICT", f"订单 {order.order_no} 状态不允许支付成功", 409)

        group.status = PaymentGroup.Status.PAID
        group.transaction_id = transaction_id
        group.paid_at = timezone.now()
        group.save(update_fields=["status", "transaction_id", "paid_at", "updated_at"])

        for order in orders:
            order.paid_amount = order.payable_amount
            order.save(update_fields=["paid_amount", "updated_at"])
            transit_order(order.id, "PAY_SUCCESS", operator_type="SYSTEM")
            entries = [
                {
                    "account_type": AccountType.PLATFORM_CASH,
                    "account_id": 0,
                    "direction": Direction.DEBIT,
                    "amount": order.payable_amount,
                },
                {
                    "account_type": AccountType.MERCHANT_PENDING,
                    "account_id": order.merchant_id,
                    "direction": Direction.CREDIT,
                    "amount": order.payable_amount + order.platform_subsidy_amount,
                },
            ]
            if order.platform_subsidy_amount > 0:
                entries.append(
                    {
                        "account_type": AccountType.PLATFORM_MARKETING_EXPENSE,
                        "account_id": 0,
                        "direction": Direction.DEBIT,
                        "amount": order.platform_subsidy_amount,
                    }
                )
            post_transaction(
                biz_type="PAYMENT",
                biz_id=group.id,
                event_type="PAY_SUCCESS",
                idempotency_key=f"payment:{order.order_no}",
                entries=entries,
            )
            mark_order_paid(order)
            award_for_order_payment(
                user_id=order.user_id,
                order_no=order.order_no,
                paid_amount=order.payable_amount,
                order_id=order.id,
            )
    return group


def upsert_payment_config(admin_user, channel, request=None, **fields) -> PlatformPaymentConfig:
    """写入平台支付配置：密钥与证书加密存储，响应只返回可公开字段。"""
    require_platform_admin(admin_user)
    with transaction.atomic():
        config, created = PlatformPaymentConfig.objects.update_or_create(
            channel=channel,
            defaults={
                **fields,
                "updated_by_id": admin_user.id,
                "updated_by_name": getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", "") or "",
            },
        )
        log_operation(
            operator=admin_user,
            action="PAYMENT_CONFIG_UPDATE",
            biz_type="PAYMENT_CONFIG",
            biz_id=config.id,
            after={"channel": channel, "created": created, "enabled": config.enabled},
            request=request,
        )
    return config
