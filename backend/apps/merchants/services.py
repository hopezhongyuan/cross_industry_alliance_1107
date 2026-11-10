"""佣金解析、商户身份解析、商户创建与状态迁移。"""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.api import ApiError
from apps.common.utils import generate_no
from apps.governance.services import log_operation, require_platform_admin
from apps.ledger.services import ensure_account

from .models import Merchant, MerchantQualification, MerchantStaff

# 与技术方案一致：PENDING → ACTIVE → RESTING / BANNED；ACTIVE ↔ RESTING；BANNED → ACTIVE。
# REJECTED 由审核驳回写入，状态接口不接受。
MERCHANT_TRANSITIONS = {
    Merchant.Status.PENDING: set(),
    Merchant.Status.ACTIVE: {Merchant.Status.RESTING, Merchant.Status.BANNED},
    Merchant.Status.RESTING: {Merchant.Status.ACTIVE},
    Merchant.Status.BANNED: {Merchant.Status.ACTIVE},
    Merchant.Status.REJECTED: set(),
}


def change_merchant_status(admin_user, merchant_id: int, target_status: str, reason: str, request=None):
    """平台变更商户状态；同状态重复提交幂等返回 unchanged=False。"""
    require_platform_admin(admin_user)
    if target_status not in (Merchant.Status.ACTIVE, Merchant.Status.RESTING, Merchant.Status.BANNED):
        raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
    if not reason.strip():
        raise ApiError("VALIDATION_ERROR", "原因必填", 422)
    with transaction.atomic():
        merchant = Merchant.objects.select_for_update().filter(pk=merchant_id).first()
        if merchant is None:
            raise ApiError("NOT_FOUND", "商户不存在", 404)
        if merchant.status == target_status:
            return merchant, False
        if target_status not in MERCHANT_TRANSITIONS.get(merchant.status, set()):
            raise ApiError(
                "MERCHANT_STATE_CONFLICT",
                f"商户处于 {merchant.status}，不接受迁移至 {target_status}",
                409,
            )
        before_status = merchant.status
        merchant.status = target_status
        update_fields = ["status", "updated_at"]
        if target_status == Merchant.Status.ACTIVE and merchant.opened_at is None:
            merchant.opened_at = timezone.now()
            update_fields.append("opened_at")
        merchant.save(update_fields=update_fields)
        log_operation(
            operator=admin_user,
            action="MERCHANT_STATUS",
            biz_type="MERCHANT",
            biz_id=merchant.id,
            before={"status": before_status},
            after={"status": target_status},
            reason=reason,
            request=request,
        )
    return merchant, True


def create_merchant(admin_user, payload: dict, idempotency_key: str, request=None):
    """平台创建商户：固定直接营业，必须绑定已有负责人，同幂等键重复返回同一商户。"""
    require_platform_admin(admin_user)
    if not idempotency_key:
        raise ApiError("VALIDATION_ERROR", "缺少 Idempotency-Key", 422)

    from apps.accounts.models import AppUser

    owner = AppUser.objects.filter(phone=payload["owner_phone"], status=AppUser.Status.ACTIVE).first()
    if owner is None:
        raise ApiError("VALIDATION_ERROR", "负责人手机号未注册或已停用", 422)

    existing = Merchant.objects.filter(create_idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing, False

    data = dict(payload)
    qualifications = data.pop("qualifications", [])
    data.pop("owner_phone", None)
    try:
        with transaction.atomic():
            merchant = Merchant.objects.create(
                merchant_no=generate_no("M", 4),
                status=Merchant.Status.ACTIVE,
                opened_at=timezone.now(),
                create_idempotency_key=idempotency_key,
                **data,
            )
            ensure_account(merchant.id)
            MerchantStaff.objects.create(
                merchant=merchant,
                user=owner,
                role=MerchantStaff.Role.OWNER,
                status=MerchantStaff.Status.ACTIVE,
                joined_at=timezone.now(),
            )
            for item in qualifications:
                MerchantQualification.objects.create(merchant=merchant, **item)
            log_operation(
                operator=admin_user,
                action="MERCHANT_CREATE",
                biz_type="MERCHANT",
                biz_id=merchant.id,
                after={"merchant_no": merchant.merchant_no, "status": merchant.status, "owner_id": owner.id},
                request=request,
            )
    except IntegrityError:
        existing = Merchant.objects.filter(create_idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing, False
        raise
    return merchant, True


def update_merchant_location(admin_user, merchant_id: int, data: dict, request=None):
    """平台设置商户真实定位；经纬度同时保存，坐标统一为 GCJ-02。"""
    require_platform_admin(admin_user)
    with transaction.atomic():
        merchant = Merchant.objects.select_for_update().filter(pk=merchant_id).first()
        if merchant is None:
            raise ApiError("NOT_FOUND", "商户不存在", 404)
        before = {
            "lng": str(merchant.lng) if merchant.lng is not None else None,
            "lat": str(merchant.lat) if merchant.lat is not None else None,
            "address": merchant.address,
        }
        for field in ("lng", "lat", "province", "city", "district", "address"):
            if field in data:
                setattr(merchant, field, data[field])
        merchant.save(update_fields=["lng", "lat", "province", "city", "district", "address", "updated_at"])
        log_operation(
            operator=admin_user,
            action="MERCHANT_LOCATION_UPDATE",
            biz_type="MERCHANT",
            biz_id=merchant.id,
            before=before,
            after={
                "lng": str(merchant.lng) if merchant.lng is not None else None,
                "lat": str(merchant.lat) if merchant.lat is not None else None,
                "address": merchant.address,
            },
            request=request,
        )
    return merchant


def update_merchant_profile(admin_user, merchant_id: int, data: dict, request=None):
    """平台维护商户归类信息（行业、配送费），仅后台可见。"""
    require_platform_admin(admin_user)
    with transaction.atomic():
        merchant = Merchant.objects.select_for_update().filter(pk=merchant_id).first()
        if merchant is None:
            raise ApiError("NOT_FOUND", "商户不存在", 404)
        before = {"industry": merchant.industry, "delivery_fee": merchant.delivery_fee}
        update_fields = []
        for field in ("industry", "delivery_fee"):
            if field in data:
                setattr(merchant, field, data[field])
                update_fields.append(field)
        if update_fields:
            merchant.save(update_fields=[*update_fields, "updated_at"])
            log_operation(
                operator=admin_user,
                action="MERCHANT_PROFILE_UPDATE",
                biz_type="MERCHANT",
                biz_id=merchant.id,
                before=before,
                after={"industry": merchant.industry, "delivery_fee": merchant.delivery_fee},
                request=request,
            )
    return merchant


def resolve_commission_rate(merchant: Merchant) -> Decimal:
    """返回下单时应快照的佣金率；两者都未配置时为 0。"""
    if merchant.commission_rate is not None:
        return merchant.commission_rate
    if merchant.category_id:
        return merchant.category.commission_rate
    return Decimal("0")


def get_active_staff_merchant(user) -> Merchant:
    """商户端数据隔离入口：取当前用户有效员工身份对应的门店。"""
    role = user.merchant_staff_roles.filter(status=MerchantStaff.Status.ACTIVE).select_related("merchant").first()
    if role is None:
        raise ApiError("PERMISSION_DENIED", "需要商户身份", 403)
    if role.merchant.status != Merchant.Status.ACTIVE:
        raise ApiError("MERCHANT_NOT_AVAILABLE", "商户未营业或被冻结", 409)
    return role.merchant


def get_merchant_manager(user) -> Merchant:
    """商品发布/编辑入口：仅店主或店长，且商户营业中。"""
    role = (
        user.merchant_staff_roles.filter(
            status=MerchantStaff.Status.ACTIVE,
            role__in=(MerchantStaff.Role.OWNER, MerchantStaff.Role.MANAGER),
        )
        .select_related("merchant")
        .first()
    )
    if role is None:
        raise ApiError("PERMISSION_DENIED", "需要店主或店长权限", 403)
    if role.merchant.status != Merchant.Status.ACTIVE:
        raise ApiError("MERCHANT_NOT_AVAILABLE", "商户未营业或被冻结", 409)
    return role.merchant
