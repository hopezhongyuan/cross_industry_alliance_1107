"""规则版本、审核任务、操作日志与内容位。

规则版本用于给订单/售后/结算提供不可变快照；操作日志只追加。
"""

from django.db import models

from apps.common.fields import EncryptedTextField
from apps.common.models import TimeStampedModel


class RuleVersion(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "草稿"
        ACTIVE = "ACTIVE", "生效中"
        RETIRED = "RETIRED", "已失效"

    version_no = models.CharField("版本号", max_length=32, unique=True)
    snapshot_json = models.JSONField("规则快照", default=dict)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    effective_at = models.DateTimeField("生效时间", null=True, blank=True)
    created_by_id = models.BigIntegerField("创建人 ID", null=True, blank=True)
    created_by_name = models.CharField("创建人", max_length=60, blank=True, default="")
    remark = models.CharField("说明", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "规则版本"
        verbose_name_plural = "规则版本"
        db_table = "rule_version"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["status", "effective_at"], name="ix_rule_status_effective")]

    def __str__(self):
        return self.version_no


class AuditTask(TimeStampedModel):
    class BizType(models.TextChoices):
        MERCHANT = "MERCHANT", "商户入驻"
        PRODUCT = "PRODUCT", "商品上架"
        REVIEW = "REVIEW", "评价内容"
        QUALIFICATION = "QUALIFICATION", "资质材料"

    class Status(models.TextChoices):
        PENDING = "PENDING", "待审核"
        PROCESSING = "PROCESSING", "审核中"
        APPROVED = "APPROVED", "已通过"
        REJECTED = "REJECTED", "已驳回"
        CANCELLED = "CANCELLED", "已取消"

    biz_type = models.CharField("业务类型", max_length=20, choices=BizType.choices, db_index=True)
    biz_id = models.BigIntegerField("业务单据 ID")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    decision = models.CharField("审核结论", max_length=16, blank=True, default="")
    reason = models.CharField("审核意见", max_length=200, blank=True, default="")
    assigned_to_id = models.BigIntegerField("审核人 ID", null=True, blank=True)
    assigned_to_name = models.CharField("审核人", max_length=60, blank=True, default="")
    handled_at = models.DateTimeField("处理时间", null=True, blank=True)

    class Meta:
        verbose_name = "审核任务"
        verbose_name_plural = "审核任务"
        db_table = "audit_task"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["biz_type", "status", "created_at"], name="ix_audit_biz_status_created"),
            models.Index(fields=["assigned_to_id", "status"], name="ix_audit_assignee_status"),
        ]

    def __str__(self):
        return f"{self.biz_type}-{self.biz_id}-{self.status}"


class OperationLog(TimeStampedModel):
    operator_id = models.BigIntegerField("操作人 ID", null=True, blank=True)
    operator_name = models.CharField("操作人", max_length=60, blank=True, default="")
    action = models.CharField("动作", max_length=40, db_index=True)
    biz_type = models.CharField("业务类型", max_length=24, blank=True, default="")
    biz_id = models.BigIntegerField("业务单据 ID", null=True, blank=True)
    before_json = models.JSONField("变更前", default=dict, blank=True)
    after_json = models.JSONField("变更后", default=dict, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("UA", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"
        db_table = "operation_log"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["biz_type", "biz_id", "created_at"], name="ix_oplog_biz_created")]

    def __str__(self):
        return f"{self.operator_name}-{self.action}"


class ContentItem(TimeStampedModel):
    class SlotCode(models.TextChoices):
        HOME_BANNER = "HOME_BANNER", "首页 Banner"
        HOME_RECOMMEND = "HOME_RECOMMEND", "首页推荐位"
        CATEGORY_ENTRY = "CATEGORY_ENTRY", "类目入口"
        MERCHANT_FEATURE = "MERCHANT_FEATURE", "商户精选"

    class Status(models.TextChoices):
        ENABLED = "ENABLED", "展示中"
        DISABLED = "DISABLED", "已下线"

    slot_code = models.CharField("内容位", max_length=24, choices=SlotCode.choices, db_index=True)
    title = models.CharField("标题", max_length=80, blank=True, default="")
    image_url = models.URLField("图片", blank=True, default="")
    link_url = models.CharField("跳转链接", max_length=200, blank=True, default="")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ENABLED, db_index=True)
    sort = models.IntegerField("排序", default=0)
    start_at = models.DateTimeField("开始展示", null=True, blank=True)
    end_at = models.DateTimeField("结束展示", null=True, blank=True)

    class Meta:
        verbose_name = "内容位"
        verbose_name_plural = "内容位"
        db_table = "content_item"
        ordering = ("slot_code", "sort", "id")
        indexes = [models.Index(fields=["slot_code", "status", "sort"], name="ix_content_slot_status_sort")]

    def __str__(self):
        return f"{self.slot_code}-{self.title}"


class PlatformConfig(TimeStampedModel):
    """平台基础信息与渠道参数：单例配置，密钥类字段加密存储。"""

    singleton_key = models.CharField("单例键", max_length=20, unique=True, default="default", editable=False)
    platform_name = models.CharField("平台名称", max_length=80, default="异业联盟")
    logo_url = models.CharField("Logo", max_length=300, blank=True, default="")
    contact_phone = models.CharField("联系电话", max_length=20, blank=True, default="")
    company_name = models.CharField("公司主体", max_length=120, blank=True, default="")
    icp_no = models.CharField("ICP备案号", max_length=80, blank=True, default="")
    privacy_policy = models.TextField("隐私协议", blank=True, default="")
    user_agreement = models.TextField("用户注册协议", blank=True, default="")
    agreement_version = models.CharField("协议版本", max_length=32, blank=True, default="")
    miniapp_app_id = models.CharField("小程序 AppID", max_length=64, blank=True, default="")
    miniapp_app_secret = EncryptedTextField("小程序 AppSecret", blank=True, default="")
    miniapp_original_id = models.CharField("小程序原始 ID", max_length=64, blank=True, default="")
    amap_web_key = EncryptedTextField("高德 Web 服务 Key", blank=True, default="")
    amap_js_key = models.CharField("高德 JS API Key", max_length=100, blank=True, default="")
    amap_js_security_code = EncryptedTextField("高德 JS 安全密钥", blank=True, default="")
    amap_enabled = models.BooleanField("启用高德地图", default=False)
    updated_by_name = models.CharField("最后修改人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "平台配置"
        verbose_name_plural = "平台配置"
        db_table = "platform_config"

    def __str__(self):
        return self.platform_name


class StoreNavItem(TimeStampedModel):
    """消费者端底部导航：平台统一配置，最多 5 项。"""

    class LinkType(models.TextChoices):
        FUNCTION = "FUNCTION", "功能页面"
        MICRO_PAGE = "MICRO_PAGE", "微页面"
        CATEGORY = "CATEGORY", "商品类目"
        MERCHANT = "MERCHANT", "商户"
        PRODUCT = "PRODUCT", "商品"

    class Status(models.TextChoices):
        ENABLED = "ENABLED", "启用"
        DISABLED = "DISABLED", "停用"

    title = models.CharField("名称", max_length=20)
    icon_selected = models.CharField("选中图标", max_length=300, blank=True, default="")
    icon_unselected = models.CharField("未选中图标", max_length=300, blank=True, default="")
    link_type = models.CharField("链接类型", max_length=16, choices=LinkType.choices, default=LinkType.FUNCTION)
    link_value = models.CharField("链接目标", max_length=200, blank=True, default="")
    sort = models.PositiveSmallIntegerField("排序", default=0)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ENABLED)
    updated_by_name = models.CharField("最后修改人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "底部导航"
        verbose_name_plural = "底部导航"
        db_table = "store_nav_item"
        ordering = ("sort", "id")

    def __str__(self):
        return self.title


class DecoPage(TimeStampedModel):
    """平台微页面：草稿与已发布快照分离，发布后消费者端只读已发布内容。"""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "草稿"
        PUBLISHED = "PUBLISHED", "已发布"

    slug = models.CharField("页面标识", max_length=40, unique=True)
    title = models.CharField("页面标题", max_length=80)
    share_title = models.CharField("分享标题", max_length=80, blank=True, default="")
    share_image = models.CharField("分享图", max_length=300, blank=True, default="")
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    draft_components = models.JSONField("草稿组件", default=list, blank=True)
    published_components = models.JSONField("已发布组件", default=list, blank=True)
    published_at = models.DateTimeField("发布时间", null=True, blank=True)
    updated_by_name = models.CharField("最后修改人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "微页面"
        verbose_name_plural = "微页面"
        db_table = "deco_page"
        ordering = ("-updated_at", "-id")

    def __str__(self):
        return f"{self.slug}-{self.title}"


class MediaFolder(TimeStampedModel):
    """素材文件夹：仅一级，平台后台维护。"""

    name = models.CharField("文件夹名", max_length=60, unique=True)
    sort = models.IntegerField("排序", default=0)
    created_by_name = models.CharField("创建人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "素材文件夹"
        verbose_name_plural = "素材文件夹"
        db_table = "media_folder"
        ordering = ("sort", "id")

    def __str__(self):
        return self.name


class MediaAsset(TimeStampedModel):
    class Kind(models.TextChoices):
        IMAGE = "IMAGE", "图片"
        VIDEO = "VIDEO", "视频"

    folder = models.ForeignKey(
        MediaFolder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
        verbose_name="文件夹",
    )
    kind = models.CharField("类型", max_length=8, choices=Kind.choices, db_index=True)
    file = models.FileField("文件", upload_to="%Y/%m/")
    name = models.CharField("素材名", max_length=120, blank=True, default="")
    original_name = models.CharField("原始文件名", max_length=200, blank=True, default="")
    mime = models.CharField("MIME", max_length=100, blank=True, default="")
    size = models.BigIntegerField("大小（字节）", default=0)
    width = models.PositiveIntegerField("宽", null=True, blank=True)
    height = models.PositiveIntegerField("高", null=True, blank=True)
    duration_ms = models.PositiveIntegerField("时长（毫秒）", null=True, blank=True)
    created_by_name = models.CharField("上传人", max_length=60, blank=True, default="")

    class Meta:
        verbose_name = "素材"
        verbose_name_plural = "素材"
        db_table = "media_asset"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["folder", "kind", "created_at"], name="ix_media_folder_kind_created")]

    def __str__(self):
        return self.name or self.original_name
