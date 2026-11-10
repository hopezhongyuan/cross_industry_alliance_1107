"""商户端订单履约：接单、拒单、发货/备货、核销。"""

from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError
from apps.fulfillment.models import Appointment, OrderDelivery, VerifyCode
from apps.ledger.services import create_settlement_item
from apps.merchants.services import get_active_staff_merchant
from apps.payments.refund_services import refund_order

from .models import Order
from .services import transit_order


def _get_order(merchant, order_id) -> Order:
    order = Order.objects.filter(pk=order_id, merchant=merchant).first()
    if order is None:
        raise ApiError("NOT_FOUND", "订单不存在", 404)
    return order


def accept_order(user, order_id):
    merchant = get_active_staff_merchant(user)
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, merchant=merchant).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        if order.status != Order.Status.PENDING_ACCEPT:
            raise ApiError("ORDER_STATE_CONFLICT", "当前状态不允许接单", 409)
        order = transit_order(order.id, "MERCHANT_ACCEPT", operator_type="MERCHANT", operator_id=user.id)
    return order


def reject_order(user, order_id, reason: str):
    merchant = get_active_staff_merchant(user)
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, merchant=merchant).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        if order.status != Order.Status.PENDING_ACCEPT:
            raise ApiError("ORDER_STATE_CONFLICT", "当前状态不允许拒单", 409)
        refund_order(
            order.id,
            order.paid_amount - order.refunded_amount,
            reason,
            reject_event="MERCHANT_REJECT",
        )
        order.refresh_from_db()
    return order


def ship_order(user, order_id, logistics_company="", logistics_no=""):
    merchant = get_active_staff_merchant(user)
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, merchant=merchant).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        if order.status != Order.Status.PENDING_FULFILL:
            raise ApiError("ORDER_STATE_CONFLICT", "当前状态不允许发货", 409)

        if order.order_type in (Order.Type.EXPRESS, Order.Type.STORE_DELIVERY):
            OrderDelivery.objects.filter(order=order).update(
                logistics_company=logistics_company,
                logistics_no=logistics_no,
                shipped_at=timezone.now(),
            )
            order = transit_order(order.id, "SHIP", operator_type="MERCHANT", operator_id=user.id)
        elif order.order_type == Order.Type.PICKUP:
            order = transit_order(order.id, "PICKUP_READY", operator_type="MERCHANT", operator_id=user.id)
        elif order.order_type == Order.Type.SERVICE:
            Appointment.objects.filter(order=order).update(
                status=Appointment.Status.CONFIRMED, confirmed_at=timezone.now()
            )
            order = transit_order(order.id, "APPOINTMENT_CONFIRM", operator_type="MERCHANT", operator_id=user.id)
        else:
            raise ApiError("ORDER_STATE_CONFLICT", "卡券订单到店核销即可，无需发货", 409)
    return order


def verify_code(user, code: str):
    merchant = get_active_staff_merchant(user)
    with transaction.atomic():
        verify = (
            VerifyCode.objects.select_for_update().filter(code=code, merchant=merchant).select_related("order").first()
        )
        if verify is None:
            raise ApiError("VERIFY_CODE_INVALID", "核销码不存在或不属于本店", 409)
        if verify.status != VerifyCode.Status.ACTIVE:
            raise ApiError("VERIFY_CODE_INVALID", "核销码已使用或已失效", 409)
        if verify.valid_to and timezone.now() > verify.valid_to:
            raise ApiError("VERIFY_CODE_INVALID", "核销码已过期", 409)

        order = Order.objects.select_for_update().filter(pk=verify.order_id).first()
        if order is None or order.merchant_id != merchant.id:
            raise ApiError("VERIFY_CODE_INVALID", "核销码不属于本店订单", 409)

        # 先标记本码已核销，再判断订单是否还有未核销的码
        verify.status = VerifyCode.Status.USED
        verify.used_at = timezone.now()
        verify.used_by_id = user.id
        verify.used_by_name = user.username if hasattr(user, "username") else ""
        verify.save(update_fields=["status", "used_at", "used_by_id", "used_by_name", "updated_at"])

        if order.order_type == Order.Type.COUPON:
            remaining = VerifyCode.objects.filter(order=order, status=VerifyCode.Status.ACTIVE).exists()
            if remaining:
                # 还有未核销的码：订单保持待履约，不触发状态迁移
                return order
            event = "SERVICE_VERIFY"
        elif order.order_type == Order.Type.SERVICE and order.status == Order.Status.PENDING_FULFILL:
            event = "SERVICE_VERIFY"
        elif order.status == Order.Status.FULFILLING:
            event = "PICKUP_VERIFY" if order.order_type == Order.Type.PICKUP else "SERVICE_VERIFY"
        else:
            raise ApiError("ORDER_STATE_CONFLICT", "当前订单状态不允许核销", 409)

        order = transit_order(order.id, event, operator_type="MERCHANT", operator_id=user.id)
        order.refresh_from_db()
        create_settlement_item(order)
    return order
