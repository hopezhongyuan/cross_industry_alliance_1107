"""优惠券服务：领券、可用券校验、锁定/释放、过期处理。

写入口：
- claim_coupon：领取券（库存+限领控制）
- lock_user_coupon：下单锁定为 USED
- release_user_coupon：订单关闭/取消退回 UNUSED
- mark_user_coupon_used：支付成功确认（实际 lock 已置 USED，此为幂等兜底）
- expire_coupons：定时过期
"""

from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError

from .models import Coupon, UserCoupon


class CouponError(Exception):
    pass


def claim_coupon(user, coupon_id: int) -> UserCoupon:
    """领取优惠券。"""
    now = timezone.now()
    with transaction.atomic():
        coupon = Coupon.objects.select_for_update().filter(pk=coupon_id).first()
        if coupon is None:
            raise ApiError("COUPON_NOT_FOUND", "优惠券不存在", 404)
        if coupon.status != Coupon.Status.ACTIVE:
            raise ApiError("COUPON_NOT_AVAILABLE", "优惠券不可领取", 409)
        if now < coupon.valid_from or now > coupon.valid_to:
            raise ApiError("COUPON_EXPIRED", "优惠券不在有效期内", 409)
        if coupon.total_stock > 0 and coupon.issued_count >= coupon.total_stock:
            raise ApiError("COUPON_OUT_OF_STOCK", "优惠券已领完", 409)
        if coupon.per_user_limit > 0:
            claimed = UserCoupon.objects.filter(user=user, coupon=coupon).count()
            if claimed >= coupon.per_user_limit:
                raise ApiError("COUPON_CLAIM_LIMIT", "已达领取上限", 409)

        coupon.issued_count += 1
        coupon.save(update_fields=["issued_count", "updated_at"])
        user_coupon = UserCoupon.objects.create(
            coupon=coupon, user=user, status=UserCoupon.Status.UNUSED, expire_at=coupon.valid_to
        )
    return user_coupon


def list_user_coupons(user, status: str = None) -> list:
    qs = UserCoupon.objects.filter(user=user).select_related("coupon").order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    return list(qs)


def get_available_coupons(user, *, merchant_id: int, product_ids: list, amount: int) -> list:
    """返回用户在指定商户/商品下可用的券。

    匹配规则：
    - 平台券：商户在 target_merchants 内（或 ALL 不指定商户），商品类目/商品匹配；
    - 商户券：coupon.merchant_id == merchant_id，商品匹配；
    - 门槛：amount（商品金额） >= min_amount。
    """
    now = timezone.now()
    from apps.catalog.models import Product

    products = {p.id: p for p in Product.objects.filter(pk__in=product_ids)}
    if not products:
        return []

    qs = (
        UserCoupon.objects.filter(
            user=user,
            status=UserCoupon.Status.UNUSED,
            expire_at__gt=now,
            coupon__status=Coupon.Status.ACTIVE,
        )
        .select_related("coupon")
        .order_by("-coupon__face_value")
    )
    results = []
    for uc in qs:
        coupon = uc.coupon
        # 商户范围
        if coupon.type == Coupon.Type.MERCHANT:
            if coupon.merchant_id != merchant_id:
                continue
        else:
            if coupon.target_merchants.exists() and not coupon.target_merchants.filter(pk=merchant_id).exists():
                continue
        # 商品范围
        if not _match_scope(coupon, products):
            continue
        # 门槛（按商品金额）
        if amount < coupon.min_amount:
            continue
        results.append(uc)
    return results


def _match_scope(coupon: Coupon, products: dict) -> bool:
    if coupon.scope_type == Coupon.ScopeType.ALL:
        return True
    if coupon.scope_type == Coupon.ScopeType.CATEGORY:
        cat_ids = set(coupon.scope_category_ids or [])
        return any(p.category_id in cat_ids for p in products.values())
    if coupon.scope_type == Coupon.ScopeType.PRODUCT:
        prod_ids = set(coupon.scope_product_ids or [])
        return any(pid in prod_ids for pid in products)
    return True


def compute_discount(coupon: Coupon, amount: int) -> int:
    """计算优惠金额：min(face_value, max(0, amount - min_amount))。"""
    if amount < coupon.min_amount:
        return 0
    return (
        min(coupon.face_value, max(0, amount - coupon.min_amount))
        if coupon.min_amount > 0
        else min(coupon.face_value, amount)
    )


def lock_user_coupon(user, user_coupon_id: int, *, merchant_id: int, product_ids: list, amount: int):
    """下单时锁定券为 USED，返回 (user_coupon, discount_amount)。"""
    now = timezone.now()
    with transaction.atomic():
        uc = (
            UserCoupon.objects.select_for_update()
            .filter(pk=user_coupon_id, user=user, status=UserCoupon.Status.UNUSED)
            .select_related("coupon")
            .first()
        )
        if uc is None:
            raise ApiError("COUPON_NOT_AVAILABLE", "优惠券不可用", 409)
        coupon = uc.coupon
        if coupon.status != Coupon.Status.ACTIVE or now > coupon.valid_to or now < coupon.valid_from:
            raise ApiError("COUPON_EXPIRED", "优惠券已失效", 409)
        # 范围校验
        if coupon.type == Coupon.Type.MERCHANT:
            if coupon.merchant_id != merchant_id:
                raise ApiError("COUPON_SCOPE_MISMATCH", "优惠券不适用该商户", 409)
        else:
            if coupon.target_merchants.exists() and not coupon.target_merchants.filter(pk=merchant_id).exists():
                raise ApiError("COUPON_SCOPE_MISMATCH", "优惠券不适用该商户", 409)
        from apps.catalog.models import Product

        products = {p.id: p for p in Product.objects.filter(pk__in=product_ids)}
        if not _match_scope(coupon, products):
            raise ApiError("COUPON_SCOPE_MISMATCH", "优惠券不适用该商品", 409)
        discount = compute_discount(coupon, amount)
        if discount <= 0:
            raise ApiError("COUPON_THRESHOLD_NOT_MET", "未达到使用门槛", 409)
        uc.status = UserCoupon.Status.USED
        uc.save(update_fields=["status", "updated_at"])
    return uc, discount


def release_user_coupon_by_order(order_id: int) -> None:
    """订单关闭/取消时退回券。"""
    with transaction.atomic():
        uc = UserCoupon.objects.select_for_update().filter(order_id=order_id, status=UserCoupon.Status.USED).first()
        if uc is None:
            return
        if uc.expire_at and uc.expire_at <= timezone.now():
            uc.status = UserCoupon.Status.EXPIRED
        else:
            uc.status = UserCoupon.Status.UNUSED
        uc.order_id = None
        uc.order_no = ""
        uc.used_at = None
        uc.save(update_fields=["status", "order_id", "order_no", "used_at", "updated_at"])


def bind_user_coupon_order(user_coupon_id: int, order_id: int, order_no: str) -> None:
    """支付成功后绑定订单信息（lock 时未填 order_id，此处补全）。"""
    UserCoupon.objects.filter(pk=user_coupon_id).update(order_id=order_id, order_no=order_no, used_at=timezone.now())


def expire_coupons() -> int:
    """将过期未使用的券置为 EXPIRED，返回处理数量。"""
    now = timezone.now()
    count = UserCoupon.objects.filter(status=UserCoupon.Status.UNUSED, expire_at__lte=now).update(
        status=UserCoupon.Status.EXPIRED, updated_at=now
    )
    return count
