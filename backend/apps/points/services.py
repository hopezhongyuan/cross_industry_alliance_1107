"""积分服务：唯一写入口，负责幂等、余额快照与负数校验。"""

from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError

from .models import PointsConfig, PointTransaction, UserPointAccount


class PointsError(Exception):
    """积分业务错误。"""


def get_config() -> PointsConfig:
    config, _ = PointsConfig.objects.get_or_create(singleton_key="default")
    return config


def get_or_create_account(user_id: int) -> UserPointAccount:
    account, _ = UserPointAccount.objects.get_or_create(user_id=user_id)
    return account


def post_point_transaction(
    *,
    user_id: int,
    biz_type: str,
    delta: int,
    idempotency_key: str,
    biz_id: Optional[int] = None,
    remark: str = "",
    operator_name: str = "",
) -> PointTransaction:
    """写一条积分流水并更新账户快照。

    - delta 正为增加、负为消耗；
    - 幂等键重复时直接返回原记录，不重复发放/扣减；
    - 消耗导致余额为负时抛出 PointsError。
    """
    if delta == 0:
        raise PointsError("积分变动不能为 0")
    with transaction.atomic():
        txn, created = PointTransaction.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "user_id": user_id,
                "biz_type": biz_type,
                "delta": delta,
                "balance_after": 0,  # 占位，下面更新
                "biz_id": biz_id,
                "remark": remark,
                "operator_name": operator_name,
            },
        )
        if not created:
            return txn

        account = UserPointAccount.objects.select_for_update().get_or_create(user_id=user_id)[0]
        new_balance = account.balance + delta
        if new_balance < 0:
            raise PointsError(f"积分不足：当前 {account.balance}，变动 {delta}")

        account.balance = new_balance
        if delta > 0:
            account.total_earned += delta
        else:
            account.total_spent += -delta
        account.version += 1
        account.save(update_fields=["balance", "total_earned", "total_spent", "version", "updated_at"])

        txn.balance_after = new_balance
        txn.save(update_fields=["balance_after"])
    return txn


# ---------- 业务场景发放函数 ----------


def award_for_order_payment(
    user_id: int, order_no: str, paid_amount: int, order_id: Optional[int] = None
) -> Optional[PointTransaction]:
    """支付成功发放消费积分。paid_amount 单位为分。"""
    config = get_config()
    if not config.enabled:
        return None
    if config.consumption_rate <= 0:
        return None
    points = paid_amount // config.consumption_rate
    if config.consumption_max_per_order > 0:
        points = min(points, config.consumption_max_per_order)
    if points <= 0:
        return None
    return post_point_transaction(
        user_id=user_id,
        biz_type=PointTransaction.BizType.CONSUMPTION,
        delta=points,
        idempotency_key=f"points:order:{order_no}",
        biz_id=order_id,
        remark=f"消费 {paid_amount} 分返 {points} 积分",
    )


def award_for_register(user_id: int) -> Optional[PointTransaction]:
    """新用户注册赠送积分。"""
    config = get_config()
    if not config.enabled or config.register_points <= 0:
        return None
    return post_point_transaction(
        user_id=user_id,
        biz_type=PointTransaction.BizType.REGISTER,
        delta=config.register_points,
        idempotency_key=f"points:register:{user_id}",
        remark=f"注册赠送 {config.register_points} 积分",
    )


def signin(user_id: int) -> PointTransaction:
    """签到；同一用户每日仅一次，重复调用幂等返回。"""
    config = get_config()
    if not config.enabled or config.signin_points <= 0:
        raise ApiError("POINTS_DISABLED", "签到积分未启用", 409)
    today = timezone.localdate().isoformat()
    return post_point_transaction(
        user_id=user_id,
        biz_type=PointTransaction.BizType.SIGNIN,
        delta=config.signin_points,
        idempotency_key=f"points:signin:{user_id}:{today}",
        remark=f"签到 +{config.signin_points}",
    )


def share(user_id: int, target_type: str, target_id: int) -> Optional[PointTransaction]:
    """分享赚积分；每日次数上限，超过则返回 None（不报错）。"""
    config = get_config()
    if not config.enabled or config.share_points <= 0:
        return None

    today = timezone.localdate().isoformat()
    prefix = f"points:share:{user_id}:{today}:"
    today_count = PointTransaction.objects.filter(
        user_id=user_id,
        biz_type=PointTransaction.BizType.SHARE,
        idempotency_key__startswith=prefix,
    ).count()
    if today_count >= config.share_daily_limit:
        return None

    seq = today_count + 1
    return post_point_transaction(
        user_id=user_id,
        biz_type=PointTransaction.BizType.SHARE,
        delta=config.share_points,
        idempotency_key=f"{prefix}{seq}",
        biz_id=target_id,
        remark=f"分享{target_type} +{config.share_points}",
    )


def award_for_review(user_id: int, order_id: int) -> Optional[PointTransaction]:
    """评价订单赠送积分；每单一次（评价本身有 unique 约束）。"""
    config = get_config()
    if not config.enabled or config.review_points <= 0:
        return None
    return post_point_transaction(
        user_id=user_id,
        biz_type=PointTransaction.BizType.REVIEW,
        delta=config.review_points,
        idempotency_key=f"points:review:{order_id}",
        biz_id=order_id,
        remark=f"评价订单 +{config.review_points}",
    )


def adjust_by_admin(
    *,
    user_id: int,
    delta: int,
    reason: str,
    operator_name: str = "",
    idempotency_key: str = "",
) -> PointTransaction:
    """后台人工调整积分，可正可负。"""
    if not reason.strip():
        raise ApiError("VALIDATION_ERROR", "调整原因必填", 422)
    if delta == 0:
        raise ApiError("VALIDATION_ERROR", "调整积分不能为 0", 422)
    return post_point_transaction(
        user_id=user_id,
        biz_type=PointTransaction.BizType.ADMIN_ADJUST,
        delta=delta,
        idempotency_key=idempotency_key or f"points:admin:{user_id}:{int(timezone.now().timestamp() * 1000)}",
        remark=reason,
        operator_name=operator_name,
    )
