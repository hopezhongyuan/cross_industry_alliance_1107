"""积分规则、用户积分账户与积分流水。

约束：
- PointTransaction 只追加，不修改不删除；
- 同一 idempotency_key 只产生一条流水；
- 积分发放与业务状态在同一事务内提交；
- 余额只能经 post_point_transaction 变更。
"""

from django.db import models

from apps.common.models import TimeStampedModel


class PointsConfig(TimeStampedModel):
    """平台积分规则：单例配置，密钥类字段不涉及。"""

    singleton_key = models.CharField("单例键", max_length=20, unique=True, default="default", editable=False)
    enabled = models.BooleanField("积分功能启用", default=True)

    consumption_rate = models.PositiveIntegerField("消费积分比例（分/积分）", default=100)
    consumption_max_per_order = models.PositiveIntegerField("单笔订单积分上限（0=不限）", default=0)

    signin_points = models.PositiveIntegerField("签到积分", default=5)
    share_points = models.PositiveIntegerField("单次分享积分", default=2)
    share_daily_limit = models.PositiveIntegerField("每日分享次数上限", default=3)
    register_points = models.PositiveIntegerField("注册积分", default=50)
    review_points = models.PositiveIntegerField("评价积分", default=3)

    updated_by_name = models.CharField("最后修改人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "积分规则"
        verbose_name_plural = "积分规则"
        db_table = "points_config"

    def __str__(self):
        return f"积分规则（启用={self.enabled}）"


class UserPointAccount(TimeStampedModel):
    """用户积分账户快照：与 PointTransaction 在同一事务内更新。"""

    user = models.OneToOneField(
        "accounts.AppUser", on_delete=models.CASCADE, related_name="point_account", verbose_name="用户"
    )
    balance = models.BigIntegerField("可用积分", default=0)
    total_earned = models.BigIntegerField("累计获得", default=0)
    total_spent = models.BigIntegerField("累计消耗", default=0)
    version = models.PositiveIntegerField("乐观锁版本", default=0)

    class Meta:
        verbose_name = "用户积分账户"
        verbose_name_plural = "用户积分账户"
        db_table = "user_point_account"
        constraints = [
            models.CheckConstraint(check=models.Q(balance__gte=0), name="ck_points_balance_nonnegative"),
        ]

    def __str__(self):
        return f"用户积分-{self.user_id}"


class PointTransaction(TimeStampedModel):
    class BizType(models.TextChoices):
        CONSUMPTION = "CONSUMPTION", "消费返积分"
        SIGNIN = "SIGNIN", "签到"
        SHARE = "SHARE", "分享"
        REGISTER = "REGISTER", "注册"
        REVIEW = "REVIEW", "评价"
        ADMIN_ADJUST = "ADMIN_ADJUST", "后台调整"

    user = models.ForeignKey(
        "accounts.AppUser", on_delete=models.CASCADE, related_name="point_transactions", verbose_name="用户"
    )
    biz_type = models.CharField("业务类型", max_length=16, choices=BizType.choices, db_index=True)
    delta = models.BigIntegerField("变动积分（正增负减）")
    balance_after = models.BigIntegerField("变动后余额")
    idempotency_key = models.CharField("幂等键", max_length=64, unique=True)
    biz_id = models.BigIntegerField("业务单据 ID", null=True, blank=True)
    remark = models.CharField("备注", max_length=200, blank=True, default="")
    operator_name = models.CharField("操作人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "积分流水"
        verbose_name_plural = "积分流水"
        db_table = "point_transaction"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["user", "biz_type", "created_at"], name="ix_point_txn_user_type_created"),
        ]

    def __str__(self):
        return f"{self.user_id}-{self.biz_type}-{self.delta}"
