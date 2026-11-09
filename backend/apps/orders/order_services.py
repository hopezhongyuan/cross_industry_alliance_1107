"""下单、取消与支付成功后的履约准备。"""

import secrets
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product, ProductSku, ServiceSlot
from apps.common.api import ApiError
from apps.fulfillment.models import Appointment, OrderDelivery, VerifyCode
from apps.merchants.models import Merchant
from apps.merchants.services import resolve_commission_rate

from .models import Order, OrderItem
from .services import transit_order
from .split_services import build_line_split


def _validate_products(merchant_id, order_type, items):
    product_ids = [item["product_id"] for item in items]
    products = {
        product.id: product for product in Product.objects.select_related("merchant").filter(pk__in=product_ids)
    }
    contexts = []
    for item in items:
        product = products.get(item["product_id"])
        if product is None or product.status != Product.Status.ON_SALE:
            raise ApiError("PRODUCT_NOT_AVAILABLE", "商品不存在或已下架", 409)
        if product.merchant_id != merchant_id:
            raise ApiError("MERCHANT_MISMATCH", "商品不属于该商户", 409)
        if order_type == Order.Type.SERVICE and product.type != Product.Type.SERVICE:
            raise ApiError("DELIVERY_TYPE_NOT_SUPPORTED", "服务订单包含实物商品", 409)
        if order_type != Order.Type.SERVICE and product.type != Product.Type.PHYSICAL:
            raise ApiError("DELIVERY_TYPE_NOT_SUPPORTED", "实物订单包含服务商品", 409)
        contexts.append({"item": item, "product": product, "sku": None})
    return contexts


def _attach_skus(contexts):
    sku_ids = [ctx["item"].get("sku_id") for ctx in contexts if ctx["item"].get("sku_id")]
    skus = {sku.id: sku for sku in ProductSku.objects.select_for_update().filter(pk__in=sku_ids)}
    for ctx in contexts:
        sku_id = ctx["item"].get("sku_id")
        if not sku_id:
            continue
        sku = skus.get(sku_id)
        if sku is None or sku.product_id != ctx["product"].id:
            raise ApiError("SKU_NOT_FOUND", "规格不存在或不属于该商品", 409)
        ctx["sku"] = sku


def _check_stock(contexts):
    need = defaultdict(int)
    for ctx in contexts:
        if ctx["sku"] is not None:
            need[ctx["sku"].id] += ctx["item"]["quantity"]
    for sku_id, quantity in need.items():
        sku = next(ctx["sku"] for ctx in contexts if ctx["sku"] and ctx["sku"].id == sku_id)
        if sku.available_stock < quantity:
            raise ApiError(
                "STOCK_NOT_ENOUGH",
                f"库存不足，当前可售 {sku.available_stock}",
                409,
                {"available_stock": sku.available_stock},
            )
    return need


def _reserve_slot(contexts, appointment):
    if not appointment:
        return None
    service_products = [ctx["product"] for ctx in contexts if ctx["product"].type == Product.Type.SERVICE]
    if not service_products:
        raise ApiError("SLOT_NOT_AVAILABLE", "该订单不支持预约", 409)
    slot = ServiceSlot.objects.select_for_update().filter(pk=appointment["slot_id"]).first()
    if slot is None or slot.product_id not in [product.id for product in service_products]:
        raise ApiError("SLOT_NOT_AVAILABLE", "预约时段不存在或不属于该商品", 409)
    if slot.slot_date < timezone.localdate() or slot.status == ServiceSlot.Status.CLOSED:
        raise ApiError("SLOT_NOT_AVAILABLE", "预约时段不可用", 409)
    if slot.remaining < 1:
        raise ApiError("SLOT_FULL", "预约时段已满", 409)
    slot.reserved_count += 1
    if slot.reserved_count >= slot.capacity:
        slot.status = ServiceSlot.Status.FULL
    slot.save(update_fields=["reserved_count", "status", "updated_at"])
    return slot


def _create_single_order(
    user,
    *,
    merchant_id,
    order_type,
    items,
    contact,
    appointment=None,
    remark="",
    idempotency_key,
    request_hash,
    payment_group=None,
    user_coupon_id=None,
):
    """创建单个订单（不开启事务，由调用方控制事务边界）。"""
    existing = Order.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        if existing.user_id != user.id or existing.idempotency_hash != request_hash:
            raise ApiError("IDEMPOTENCY_CONFLICT", "幂等键已用于不同请求", 409)
        return existing, False

    merchant = Merchant.objects.filter(pk=merchant_id, status=Merchant.Status.ACTIVE).first()
    if merchant is None:
        raise ApiError("MERCHANT_NOT_AVAILABLE", "商户不存在或未营业", 409)

    contexts = _validate_products(merchant_id, order_type, items)
    _attach_skus(contexts)
    if appointment is None and any(ctx["product"].appointment_required for ctx in contexts):
        raise ApiError("APPOINTMENT_REQUIRED", "该服务需要选择预约时段", 409)
    slot = _reserve_slot(contexts, appointment)
    sku_need = _check_stock(contexts)

    line_amounts = [
        (ctx["sku"].price if ctx["sku"] else ctx["product"].price) * ctx["item"]["quantity"] for ctx in contexts
    ]
    product_amount = sum(line_amounts)
    rate = resolve_commission_rate(merchant)

    # 优惠券处理
    from apps.coupons.models import Coupon
    from apps.coupons.services import lock_user_coupon

    discount_amount = 0
    platform_subsidy_amount = 0
    merchant_discount_amount = 0
    coupon_obj = None
    user_coupon = None
    if user_coupon_id:
        product_ids = [ctx["product"].id for ctx in contexts]
        user_coupon, discount_amount = lock_user_coupon(
            user, user_coupon_id, merchant_id=merchant_id, product_ids=product_ids, amount=product_amount
        )
        coupon_obj = user_coupon.coupon
        if coupon_obj.type == Coupon.Type.PLATFORM:
            platform_subsidy_amount = discount_amount
        else:
            merchant_discount_amount = discount_amount

    # 佣金基准：商户券按优惠后金额算，平台券按原价算
    commission_base = product_amount - merchant_discount_amount
    if merchant_discount_amount > 0:
        # 按行金额比例分摊商户优惠，得到各行佣金基准
        line_bases = _allocate_discount(line_amounts, merchant_discount_amount)
        platform_amounts, commission_amount = build_line_split(line_bases, rate)
    else:
        platform_amounts, commission_amount = build_line_split(line_amounts, rate)

    payable_amount = product_amount - discount_amount
    now = timezone.now()
    order = Order.objects.create(
        user=user,
        merchant=merchant,
        order_type=order_type,
        status=Order.Status.PENDING_PAYMENT,
        product_amount=product_amount,
        delivery_fee=0,
        payable_amount=payable_amount,
        commission_rate=rate,
        commission_amount=commission_amount,
        platform_income_amount=commission_amount,
        merchant_income_amount=commission_base - commission_amount,
        platform_subsidy_amount=platform_subsidy_amount,
        merchant_discount_amount=merchant_discount_amount,
        discount_amount=discount_amount,
        coupon=coupon_obj,
        coupon_snapshot_json=(
            {
                "coupon_no": coupon_obj.coupon_no,
                "name": coupon_obj.name,
                "type": coupon_obj.type,
                "face_value": coupon_obj.face_value,
            }
            if coupon_obj
            else {}
        ),
        contact_json=contact,
        remark=remark,
        expire_at=now + timedelta(minutes=settings.ORDER_PAYMENT_TIMEOUT_MINUTES),
        idempotency_key=idempotency_key,
        idempotency_hash=request_hash,
        payment_group=payment_group,
    )

    for index, ctx in enumerate(contexts):
        product = ctx["product"]
        sku = ctx["sku"]
        price = sku.price if sku else product.price
        quantity = ctx["item"]["quantity"]
        line_amount = price * quantity
        platform_amount = platform_amounts[index]
        line_base = line_bases[index] if merchant_discount_amount > 0 else line_amount
        OrderItem.objects.create(
            order=order,
            product=product,
            sku=sku,
            snapshot_json={
                "title": product.title,
                "cover_url": product.cover_url,
                "spec": sku.spec_json if sku else {},
                "type": product.type,
                "verify_days": product.verify_days,
            },
            title=product.title,
            price=price,
            quantity=quantity,
            amount=line_amount,
            paid_amount=line_base,
            commission_rate=rate,
            platform_amount=platform_amount,
            merchant_amount=line_base - platform_amount,
        )

    for sku_id, quantity in sku_need.items():
        sku = next(ctx["sku"] for ctx in contexts if ctx["sku"] and ctx["sku"].id == sku_id)
        sku.locked_stock += quantity
        sku.version += 1
        sku.save(update_fields=["locked_stock", "version", "updated_at"])

    if order_type in (Order.Type.EXPRESS, Order.Type.PICKUP):
        OrderDelivery.objects.create(
            order=order,
            type=order_type,
            address_snapshot=contact,
            receiver_name=contact.get("name", ""),
            receiver_phone=contact.get("phone", ""),
        )

    if slot is not None:
        Appointment.objects.create(
            order=order,
            slot=slot,
            slot_date=slot.slot_date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            status=Appointment.Status.PENDING_CONFIRM,
            remark=appointment.get("remark", ""),
        )

    # 绑定用户券到订单
    if user_coupon is not None:
        from apps.coupons.services import bind_user_coupon_order

        bind_user_coupon_order(user_coupon.id, order.id, order.order_no)

    return order, True


def _allocate_discount(line_amounts: list, discount: int) -> list:
    """按行金额比例将商户优惠分摊到各行，返回各行优惠后的金额（不低于0）。"""
    if discount <= 0 or not line_amounts:
        return list(line_amounts)
    from apps.orders.split_services import allocate_amount

    discounts = allocate_amount(discount, line_amounts, caps=line_amounts)
    return [max(amt - d, 0) for amt, d in zip(line_amounts, discounts)]


def create_order(
    user,
    *,
    merchant_id,
    order_type,
    items,
    contact,
    appointment=None,
    remark="",
    idempotency_key,
    request_hash,
    user_coupon_id=None,
):
    with transaction.atomic():
        order, created = _create_single_order(
            user,
            merchant_id=merchant_id,
            order_type=order_type,
            items=items,
            contact=contact,
            appointment=appointment,
            remark=remark,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            user_coupon_id=user_coupon_id,
        )
    return order, created


def _sum_group_amounts(groups) -> int:
    """预计算批量下单总金额（分），用于创建 PaymentGroup。"""
    product_ids = {item["product_id"] for group in groups for item in group["items"]}
    sku_ids = {item["sku_id"] for group in groups for item in group["items"] if item.get("sku_id")}
    products = {p.id: p for p in Product.objects.filter(pk__in=product_ids)}
    skus = {s.id: s for s in ProductSku.objects.filter(pk__in=sku_ids)}
    total = 0
    for group in groups:
        for item in group["items"]:
            product = products.get(item["product_id"])
            sku = skus.get(item["sku_id"]) if item.get("sku_id") else None
            price = sku.price if sku else (product.price if product else 0)
            total += price * item["quantity"]
    return total


def create_batch_orders(
    user,
    *,
    groups,
    contact,
    remark="",
    idempotency_key,
    request_hash,
):
    """批量下单：按商户拆分为多个订单，共享同一合单支付组。

    幂等键按 batch 维度：每个子单 idempotency_key = f"{idem_key}:{merchant_id}"。
    重复请求命中时返回已有订单组。任一子单校验失败整体回滚。
    """
    from apps.payments.models import PaymentGroup

    with transaction.atomic():
        prefix = f"{idempotency_key}:"
        existing_orders = list(Order.objects.filter(idempotency_key__startswith=prefix).order_by("id"))
        if existing_orders:
            sample = existing_orders[0]
            if sample.user_id != user.id or sample.idempotency_hash != request_hash:
                raise ApiError("IDEMPOTENCY_CONFLICT", "幂等键已用于不同请求", 409)
            group = sample.payment_group
            return {
                "group_no": group.group_no if group else None,
                "orders": existing_orders,
                "total_amount": sum(o.payable_amount for o in existing_orders),
                "created": False,
            }

        if not groups:
            raise ApiError("VALIDATION_ERROR", "下单商品不能为空", 422)

        total_amount = _sum_group_amounts(groups)
        group = PaymentGroup.objects.create(
            user=user,
            amount=total_amount,
            status=PaymentGroup.Status.CREATED,
            channel="",  # 支付时确定
            idempotency_key=f"batch:{idempotency_key}",
            expire_at=timezone.now() + timedelta(minutes=settings.ORDER_PAYMENT_TIMEOUT_MINUTES),
        )

        created_orders = []
        for group_payload in groups:
            merchant_id = group_payload["merchant_id"]
            order, _ = _create_single_order(
                user,
                merchant_id=merchant_id,
                order_type=group_payload["order_type"],
                items=group_payload["items"],
                contact=contact,
                appointment=group_payload.get("appointment"),
                remark=remark,
                idempotency_key=f"{prefix}{merchant_id}",
                request_hash=request_hash,
                payment_group=group,
                user_coupon_id=group_payload.get("user_coupon_id"),
            )
            created_orders.append(order)

    return {
        "group_no": group.group_no,
        "orders": created_orders,
        "total_amount": total_amount,
        "created": True,
    }


def _release_stock(order):
    need = defaultdict(int)
    for item in order.items.all():
        if item.sku_id:
            need[item.sku_id] += item.quantity
    if not need:
        return
    skus = {sku.id: sku for sku in ProductSku.objects.select_for_update().filter(pk__in=need)}
    for sku_id, quantity in need.items():
        sku = skus.get(sku_id)
        if sku is None:
            continue
        sku.locked_stock = max(sku.locked_stock - quantity, 0)
        sku.version += 1
        sku.save(update_fields=["locked_stock", "version", "updated_at"])


def _release_slot(order):
    appointment = Appointment.objects.select_for_update().filter(order=order).select_related("slot").first()
    if appointment is None or appointment.status == Appointment.Status.CANCELLED:
        return
    appointment.status = Appointment.Status.CANCELLED
    appointment.canceled_at = timezone.now()
    appointment.save(update_fields=["status", "canceled_at", "updated_at"])
    if appointment.slot_id:
        slot = appointment.slot
        slot.reserved_count = max(slot.reserved_count - 1, 0)
        if slot.status == ServiceSlot.Status.FULL and slot.remaining > 0:
            slot.status = ServiceSlot.Status.OPEN
        slot.save(update_fields=["reserved_count", "status", "updated_at"])


def _release_sold_stock(order):
    need = defaultdict(int)
    for item in order.items.all():
        if item.sku_id:
            need[item.sku_id] += item.quantity
    if not need:
        return
    skus = {sku.id: sku for sku in ProductSku.objects.select_for_update().filter(pk__in=need)}
    for sku_id, quantity in need.items():
        sku = skus.get(sku_id)
        if sku is None:
            continue
        sku.sold_stock = max(sku.sold_stock - quantity, 0)
        sku.version += 1
        sku.save(update_fields=["sold_stock", "version", "updated_at"])


def restore_order_resources(order):
    """拒单/待接单取消：把已售库存与预约时段退回。"""
    _release_stock(order)
    _release_sold_stock(order)
    _release_slot(order)


def cancel_order(user, order_id, reason=""):
    from apps.payments.models import PaymentOrder
    from apps.payments.refund_services import refund_order

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        if order.status == Order.Status.CLOSED:
            return order
        if order.status == Order.Status.PENDING_ACCEPT:
            refund_order(
                order.id,
                order.paid_amount - order.refunded_amount,
                reason or "用户取消",
                reject_event="USER_CANCEL",
            )
            order.refresh_from_db()
            return order
        if order.status != Order.Status.PENDING_PAYMENT:
            raise ApiError("ORDER_STATE_CONFLICT", "当前状态不允许取消", 409)

        transit_order(
            order.id,
            "CANCEL",
            operator_type="USER",
            operator_id=user.id,
            reason=reason,
        )
        _release_stock(order)
        _release_slot(order)
        PaymentOrder.objects.filter(
            order=order, status__in=[PaymentOrder.Status.CREATED, PaymentOrder.Status.PAYING]
        ).update(status=PaymentOrder.Status.CLOSED)
        from apps.coupons.services import release_user_coupon_by_order

        release_user_coupon_by_order(order.id)
    order.refresh_from_db()
    return order


def close_expired_orders(now=None, limit=200) -> int:
    """关闭支付超时订单，释放库存与预约时段。"""
    from apps.payments.models import PaymentOrder

    now = now or timezone.now()
    ids = list(
        Order.objects.filter(status=Order.Status.PENDING_PAYMENT, expire_at__lte=now).values_list("id", flat=True)[
            :limit
        ]
    )
    count = 0
    for pk in ids:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(pk=pk, status=Order.Status.PENDING_PAYMENT).first()
            if order is None:
                continue
            transit_order(order.id, "TIMEOUT", operator_type="SYSTEM", reason="支付超时")
            _release_stock(order)
            _release_slot(order)
            PaymentOrder.objects.filter(
                order=order, status__in=[PaymentOrder.Status.CREATED, PaymentOrder.Status.PAYING]
            ).update(status=PaymentOrder.Status.CLOSED)
            from apps.coupons.services import release_user_coupon_by_order

            release_user_coupon_by_order(order.id)
            count += 1
    return count


def confirm_order(user, order_id):
    from apps.ledger.services import create_settlement_item

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        if order.status != Order.Status.FULFILLING:
            raise ApiError("ORDER_STATE_CONFLICT", "当前状态不允许确认收货", 409)
        transit_order(order.id, "CONFIRM_RECEIVE", operator_type="USER", operator_id=user.id)
        order.refresh_from_db()
        create_settlement_item(order)
    return order


def review_order(user, order_id, score, content="", images=None):
    from datetime import timedelta

    from .models import OrderReview

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, user=user).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        if order.status != Order.Status.COMPLETED:
            raise ApiError("ORDER_STATE_CONFLICT", "只有已完成订单可以评价", 409)
        if order.completed_at and timezone.now() > order.completed_at + timedelta(days=7):
            raise ApiError("ORDER_STATE_CONFLICT", "已超出评价窗口", 409)
        if OrderReview.objects.filter(order=order, user=user).exists():
            raise ApiError("ORDER_STATE_CONFLICT", "该订单已评价", 409)
        review = OrderReview.objects.create(
            order=order,
            user=user,
            merchant=order.merchant,
            score=score,
            content=content,
            images=images or [],
        )
        # 评价赠送积分：每单一次（评价本身有 unique 约束）
        from apps.points.services import award_for_review

        award_for_review(user_id=user.id, order_id=order.id)
        return review


def mark_order_paid(order):
    """支付成功后：锁定库存转已售，生成核销码/提货码。"""
    need = defaultdict(int)
    max_verify_days = 0
    for item in order.items.all():
        if item.sku_id:
            need[item.sku_id] += item.quantity
        max_verify_days = max(max_verify_days, int(item.snapshot_json.get("verify_days", 0)))

    if need:
        skus = {sku.id: sku for sku in ProductSku.objects.select_for_update().filter(pk__in=need)}
        for sku_id, quantity in need.items():
            sku = skus.get(sku_id)
            if sku is None:
                continue
            sku.locked_stock = max(sku.locked_stock - quantity, 0)
            sku.sold_stock += quantity
            sku.version += 1
            sku.save(update_fields=["locked_stock", "sold_stock", "version", "updated_at"])

    if order.order_type not in (Order.Type.PICKUP, Order.Type.SERVICE):
        return
    if VerifyCode.objects.filter(order=order).exists():
        return

    code_type = VerifyCode.Type.PICKUP if order.order_type == Order.Type.PICKUP else VerifyCode.Type.VERIFY
    code = _generate_verify_code()
    verify_code = VerifyCode.objects.create(
        order=order,
        merchant=order.merchant,
        code=code,
        type=code_type,
        status=VerifyCode.Status.ACTIVE,
        valid_from=timezone.now(),
        valid_to=timezone.now() + timedelta(days=max(max_verify_days, 1)),
    )
    if order.order_type == Order.Type.PICKUP:
        OrderDelivery.objects.filter(order=order).update(pickup_code=verify_code.code)


def _generate_verify_code() -> str:
    for _ in range(6):
        code = f"{secrets.randbelow(10**8):08d}"
        if not VerifyCode.objects.filter(code=code).exists():
            return code
    raise ApiError("VERIFY_CODE_GENERATE_FAILED", "核销码生成失败，请重试", 500)
