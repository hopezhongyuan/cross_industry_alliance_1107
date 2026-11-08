"""佣金解析与商户身份解析。"""

from decimal import Decimal

from apps.common.api import ApiError

from .models import Merchant, MerchantStaff


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
