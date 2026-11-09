"""优惠券服务：领券、可用券校验、锁定/释放、过期处理。

写入口：
- claim_coupon：领取券（库存+限领控制）
- lock_user_coupon：单订单锁定券为 USED
- lock_user_coupon_for_batch：跨商户平台券锁定并按商户分摊优惠
- release_user_coupon_by_order：订单关闭/取消/全额退款时按分摊记录释放
- expire_coupons：定时过期
"""

from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError

from .models import Coupon, CouponAllocation, UserCoupon


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


def get_available_coupons_for_batch(user, *, groups: list, total_amount: int = None) -> list:
    """跨商户合单时可用的平台券。

    groups: [{"merchant_id": int, "product_ids": [int], "amount": int}, ...]
    total_amount：合计金额（用于门槛判断）。缺省时取各商户 amount 之和。
    所有商户都需在平台券参加范围内。
    """
    now = timezone.now()
    from apps.catalog.models import Product

    all_product_ids = [pid for g in groups for pid in g["product_ids"]]
    products = {p.id: p for p in Product.objects.filter(pk__in=all_product_ids)}
    if not products:
        return []
    if total_amount is None:
        total_amount = sum(g["amount"] for g in groups)
    merchant_ids = {g["merchant_id"] for g in groups}

    qs = (
        UserCoupon.objects.filter(
            user=user,
            status=UserCoupon.Status.UNUSED,
            expire_at__gt=now,
            coupon__status=Coupon.Status.ACTIVE,
            coupon__type=Coupon.Type.PLATFORM,
        )
        .select_related("coupon")
        .order_by("-coupon__face_value")
    )
    results = []
    for uc in qs:
        coupon = uc.coupon
        # 商户范围：所有商户都必须在参加范围内（或不指定商户=全部）
        if coupon.target_merchants.exists():
            allowed = set(coupon.target_merchants.values_list("id", flat=True))
            if not merchant_ids.issubset(allowed):
                continue
        if not _match_scope(coupon, products):
            continue
        if total_amount < coupon.min_amount:
            continue
        results.append(uc)
    return results


def compute_discount(coupon: Coupon, amount: int) -> int:
    """计算满减券优惠金额：达到门槛后按面额减免（不超过订单金额）。"""
    if amount < coupon.min_amount:
        return 0
    return min(coupon.face_value, amount)


def lock_user_coupon(user, user_coupon_id: int, *, merchant_id: int, product_ids: list, amount: int):
    """单订单锁定券为 USED，返回 (user_coupon, discount_amount)。

    同时创建一条 CouponAllocation（allocated_amount = discount），
    退券统一走分摊记录释放。
    """
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
        # 创建分摊记录（单订单 = 整张券优惠都归该订单）
        CouponAllocation.objects.create(
            user_coupon=uc,
            merchant_id=merchant_id,
            allocated_amount=discount,
            status=CouponAllocation.Status.ACTIVE,
        )
    return uc, discount


def lock_user_coupon_for_batch(user, user_coupon_id: int, *, groups: list) -> dict:
    """跨商户平台券锁定并按商户商品金额比例分摊优惠。

    groups: [{"merchant_id": int, "product_ids": [int], "amount": int}, ...]
    返回 {merchant_id: allocated_amount}。

    门槛按所有商户合计金额判断；平台券需所有商户都在参加范围内。
    """
    now = timezone.now()
    if not groups:
        raise ApiError("VALIDATION_ERROR", "没有可分摊的商户", 422)
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
        if coupon.type != Coupon.Type.PLATFORM:
            raise ApiError("COUPON_SCOPE_MISMATCH", "跨商户分摊仅支持平台券", 409)
        if coupon.status != Coupon.Status.ACTIVE or now > coupon.valid_to or now < coupon.valid_from:
            raise ApiError("COUPON_EXPIRED", "优惠券已失效", 409)

        # 所有商户都必须在平台券参加范围内
        merchant_ids = [g["merchant_id"] for g in groups]
        if coupon.target_merchants.exists():
            allowed = set(coupon.target_merchants.values_list("id", flat=True))
            for mid in merchant_ids:
                if mid not in allowed:
                    raise ApiError("COUPON_SCOPE_MISMATCH", f"商户 {mid} 不在券参加范围内", 409)

        # 商品范围：券需匹配至少一个商户的商品（按 scope 宽松匹配）
        from apps.catalog.models import Product

        all_product_ids = [pid for g in groups for pid in g["product_ids"]]
        products = {p.id: p for p in Product.objects.filter(pk__in=all_product_ids)}
        if not _match_scope(coupon, products):
            raise ApiError("COUPON_SCOPE_MISMATCH", "优惠券不适用所选商品", 409)

        total_amount = sum(g["amount"] for g in groups)
        discount = compute_discount(coupon, total_amount)
        if discount <= 0:
            raise ApiError("COUPON_THRESHOLD_NOT_MET", "合计金额未达到使用门槛", 409)

        # 按各商户 amount 比例分摊（最大余数法，保证合计=discount）
        from apps.orders.split_services import allocate_amount

        weights = [g["amount"] for g in groups]
        allocated = allocate_amount(discount, weights, caps=weights)
        allocation_map = {g["merchant_id"]: allocated[i] for i, g in enumerate(groups)}

        uc.status = UserCoupon.Status.USED
        uc.save(update_fields=["status", "updated_at"])
        # 为每个商户创建分摊记录（订单创建后回填 order）
        for g, amt in zip(groups, allocated):
            if amt <= 0:
                continue
            CouponAllocation.objects.create(
                user_coupon=uc,
                merchant_id=g["merchant_id"],
                allocated_amount=amt,
                status=CouponAllocation.Status.ACTIVE,
            )
    return allocation_map


def release_user_coupon_by_order(order_id: int) -> None:
    """订单关闭/取消/全额退款时释放该订单关联的优惠券分摊。

    - 找到该订单的 ACTIVE 分摊记录，置为 RELEASED。
    - 若该用户券的所有分摊记录均已 RELEASED，则券退回 UNUSED（未过期）。
    - 兼容 P0 单订单场景（UserCoupon.order_id 直绑）。
    """
    with transaction.atomic():
        allocs = list(
            CouponAllocation.objects.select_for_update()
            .filter(order_id=order_id, status=CouponAllocation.Status.ACTIVE)
            .select_related("user_coupon")
        )
        if not allocs:
            # 兼容旧数据：直接查 UserCoupon.order_id
            uc = UserCoupon.objects.select_for_update().filter(order_id=order_id, status=UserCoupon.Status.USED).first()
            if uc is None:
                return
            _return_user_coupon(uc)
            return

        uc_ids = {a.user_coupon_id for a in allocs}
        for alloc in allocs:
            alloc.status = CouponAllocation.Status.RELEASED
            alloc.save(update_fields=["status", "updated_at"])

        # 检查每张券是否所有分摊都已释放
        for uc_id in uc_ids:
            uc = UserCoupon.objects.select_for_update().filter(pk=uc_id).first()
            if uc is None:
                continue
            active_count = CouponAllocation.objects.filter(
                user_coupon=uc, status=CouponAllocation.Status.ACTIVE
            ).count()
            if active_count == 0:
                _return_user_coupon(uc)


def _return_user_coupon(uc: UserCoupon) -> None:
    if uc.expire_at and uc.expire_at <= timezone.now():
        uc.status = UserCoupon.Status.EXPIRED
    else:
        uc.status = UserCoupon.Status.UNUSED
    uc.order_id = None
    uc.order_no = ""
    uc.used_at = None
    uc.save(update_fields=["status", "order_id", "order_no", "used_at", "updated_at"])


def bind_allocation_order(user_coupon_id: int, order_id: int, order_no: str, merchant_id: int) -> None:
    """订单创建后，把该商户对应的分摊记录回填 order 信息。"""
    CouponAllocation.objects.filter(user_coupon_id=user_coupon_id, order__isnull=True, merchant_id=merchant_id).update(
        order_id=order_id, order_no=order_no
    )


def bind_user_coupon_order(user_coupon_id: int, order_id: int, order_no: str) -> None:
    """支付成功后绑定订单信息（P0 单订单场景，order_id 直绑 UserCoupon）。"""
    UserCoupon.objects.filter(pk=user_coupon_id).update(order_id=order_id, order_no=order_no, used_at=timezone.now())


def expire_coupons() -> int:
    """将过期未使用的券置为 EXPIRED，返回处理数量。"""
    now = timezone.now()
    count = UserCoupon.objects.filter(status=UserCoupon.Status.UNUSED, expire_at__lte=now).update(
        status=UserCoupon.Status.EXPIRED, updated_at=now
    )
    return count
