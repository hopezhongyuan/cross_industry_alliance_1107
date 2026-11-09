"""优惠券模板与用户券。

- 平台券（type=PLATFORM）：平台后台创建，成本平台承担，适用指定类目/商户。
- 商户券（type=MERCHANT）：商户中心创建，成本商户承担，仅限发券商户商品。
- 优惠方式 P0 仅支持满减（face_value 面额，min_amount 门槛）。
"""

from django.db import models

from apps.common.models import TimeStampedModel
from apps.common.utils import generate_no


def default_coupon_no() -> str:
    return generate_no("CP")


def default_user_coupon_no() -> str:
    return generate_no("UC")


class Coupon(TimeStampedModel):
    class Type(models.TextChoices):
        PLATFORM = "PLATFORM", "平台券"
        MERCHANT = "MERCHANT", "商户券"

    class ScopeType(models.TextChoices):
        ALL = "ALL", "全场"
        CATEGORY = "CATEGORY", "指定类目"
        PRODUCT = "PRODUCT", "指定商品"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "草稿"
        ACTIVE = "ACTIVE", "发放中"
        PAUSED = "PAUSED", "已暂停"
        EXPIRED = "EXPIRED", "已过期"

    coupon_no = models.CharField("券编号", max_length=32, unique=True, default=default_coupon_no)
    name = models.CharField("名称", max_length=60)
    type = models.CharField("类型", max_length=16, choices=Type.choices, db_index=True)
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="coupons",
        verbose_name="发券商户（商户券必填）",
    )
    face_value = models.BigIntegerField("面额（分）")
    min_amount = models.BigIntegerField("满减门槛（分，0=无门槛）", default=0)
    scope_type = models.CharField(
        "适用范围", max_length=16, choices=ScopeType.choices, default=ScopeType.ALL, db_index=True
    )
    scope_category_ids = models.JSONField("适用类目 ID 列表", default=list, blank=True)
    scope_product_ids = models.JSONField("适用商品 ID 列表", default=list, blank=True)
    target_merchants = models.ManyToManyField(
        "merchants.Merchant", blank=True, related_name="platform_coupons", verbose_name="参加商户（平台券）"
    )
    total_stock = models.PositiveIntegerField("发放总量（0=不限）", default=0)
    issued_count = models.PositiveIntegerField("已领取数", default=0)
    per_user_limit = models.PositiveIntegerField("每人限领（0=不限）", default=1)
    valid_from = models.DateTimeField("生效时间")
    valid_to = models.DateTimeField("失效时间")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    description = models.CharField("使用说明", max_length=200, blank=True, default="")
    created_by_name = models.CharField("创建人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "优惠券"
        verbose_name_plural = "优惠券"
        db_table = "coupon"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["type", "status"], name="ix_coupon_type_status"),
            models.Index(fields=["merchant", "status"], name="ix_coupon_merchant_status"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(face_value__gt=0), name="ck_coupon_face_value_positive"),
            models.CheckConstraint(check=models.Q(min_amount__gte=0), name="ck_coupon_min_amount_nonnegative"),
        ]

    def __str__(self):
        return f"{self.coupon_no}-{self.name}"


class UserCoupon(TimeStampedModel):
    class Status(models.TextChoices):
        UNUSED = "UNUSED", "未使用"
        USED = "USED", "已使用"
        EXPIRED = "EXPIRED", "已过期"

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="user_coupons", verbose_name="优惠券")
    user = models.ForeignKey(
        "accounts.AppUser", on_delete=models.CASCADE, related_name="user_coupons", verbose_name="用户"
    )
    user_coupon_no = models.CharField("用户券编号", max_length=32, unique=True, default=default_user_coupon_no)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.UNUSED, db_index=True)
    expire_at = models.DateTimeField("过期时间")
    used_at = models.DateTimeField("使用时间", null=True, blank=True)
    order_id = models.BigIntegerField("使用订单 ID", null=True, blank=True)
    order_no = models.CharField("使用订单号", max_length=32, blank=True, default="")

    class Meta:
        verbose_name = "用户优惠券"
        verbose_name_plural = "用户优惠券"
        db_table = "user_coupon"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=["user", "coupon"], name="uq_user_coupon_user_coupon"),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="ix_user_coupon_user_status"),
            models.Index(fields=["status", "expire_at"], name="ix_user_coupon_status_expire"),
        ]

    def __str__(self):
        return f"{self.user_coupon_no}-{self.status}"
