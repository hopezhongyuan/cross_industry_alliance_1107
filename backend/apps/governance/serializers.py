"""治理接口序列化：操作日志、规则版本与审核任务。"""

from rest_framework import serializers

from .models import (
    AuditTask,
    DecoPage,
    MediaAsset,
    MediaFolder,
    OperationLog,
    PlatformConfig,
    RuleVersion,
    StoreNavItem,
)


class OperationLogSerializer(serializers.ModelSerializer):
    reason = serializers.SerializerMethodField()

    class Meta:
        model = OperationLog
        fields = ("id", "operator_name", "action", "biz_type", "biz_id", "reason", "created_at")

    def get_reason(self, obj):
        return (obj.after_json or {}).get("reason", "")


class RuleVersionInputSerializer(serializers.Serializer):
    snapshot = serializers.JSONField()
    effective_at = serializers.DateTimeField(required=False)
    remark = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class RuleVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuleVersion
        fields = ("id", "version_no", "snapshot_json", "status", "effective_at", "created_by_name", "created_at")


class AuditTaskSerializer(serializers.ModelSerializer):
    biz_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditTask
        fields = (
            "id",
            "biz_type",
            "biz_id",
            "biz_name",
            "status",
            "decision",
            "reason",
            "assigned_to_name",
            "handled_at",
            "created_at",
        )

    def get_biz_name(self, obj):
        if obj.biz_type == AuditTask.BizType.MERCHANT:
            from apps.merchants.models import Merchant

            return Merchant.objects.filter(pk=obj.biz_id).values_list("name", flat=True).first() or ""
        if obj.biz_type == AuditTask.BizType.PRODUCT:
            from apps.catalog.models import Product

            return Product.objects.filter(pk=obj.biz_id).values_list("title", flat=True).first() or ""
        return ""


class AuditDecisionInputSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=("APPROVE", "REJECT"))
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class MediaFolderSerializer(serializers.ModelSerializer):
    asset_count = serializers.SerializerMethodField()

    class Meta:
        model = MediaFolder
        fields = ("id", "name", "sort", "asset_count", "created_at")

    def get_asset_count(self, obj):
        return obj.assets.count()


class MediaFolderInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    sort = serializers.IntegerField(required=False, default=0)


class MediaAssetSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    folder_name = serializers.CharField(source="folder.name", read_only=True, default="")

    class Meta:
        model = MediaAsset
        fields = (
            "id",
            "name",
            "original_name",
            "kind",
            "url",
            "mime",
            "size",
            "width",
            "height",
            "duration_ms",
            "folder",
            "folder_name",
            "created_by_name",
            "created_at",
        )

    def get_url(self, obj):
        return obj.file.url if obj.file else ""


class MediaAssetUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    folder_id = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class AdminPlatformConfigSerializer(serializers.ModelSerializer):
    """后台读取：不回显密钥明文，只返回是否已配置。"""

    miniapp_app_secret_configured = serializers.SerializerMethodField()
    amap_web_key_configured = serializers.SerializerMethodField()
    amap_js_security_code_configured = serializers.SerializerMethodField()

    class Meta:
        model = PlatformConfig
        fields = (
            "platform_name",
            "logo_url",
            "contact_phone",
            "company_name",
            "icp_no",
            "privacy_policy",
            "user_agreement",
            "agreement_version",
            "miniapp_app_id",
            "miniapp_app_secret_configured",
            "miniapp_original_id",
            "amap_web_key_configured",
            "amap_js_key",
            "amap_js_security_code_configured",
            "amap_enabled",
            "updated_by_name",
            "updated_at",
        )

    def _configured(self, value):
        return bool(value)

    def get_miniapp_app_secret_configured(self, obj):
        return self._configured(obj.miniapp_app_secret)

    def get_amap_web_key_configured(self, obj):
        return self._configured(obj.amap_web_key)

    def get_amap_js_security_code_configured(self, obj):
        return self._configured(obj.amap_js_security_code)


class AdminPlatformConfigInputSerializer(serializers.Serializer):
    platform_name = serializers.CharField(max_length=80)
    logo_url = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    company_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    icp_no = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    privacy_policy = serializers.CharField(required=False, allow_blank=True, default="")
    user_agreement = serializers.CharField(required=False, allow_blank=True, default="")
    agreement_version = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    miniapp_app_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    miniapp_app_secret = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    miniapp_original_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    amap_web_key = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    amap_js_key = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    amap_js_security_code = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    amap_enabled = serializers.BooleanField(required=False, default=False)


class PublicPlatformConfigSerializer(serializers.ModelSerializer):
    """公开读取：只输出站点信息与前端地图所需参数。"""

    class Meta:
        model = PlatformConfig
        fields = (
            "platform_name",
            "logo_url",
            "contact_phone",
            "company_name",
            "icp_no",
            "privacy_policy",
            "user_agreement",
            "agreement_version",
            "amap_enabled",
            "amap_js_key",
            "amap_js_security_code",
        )


class StoreNavItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreNavItem
        fields = (
            "id",
            "title",
            "icon_selected",
            "icon_unselected",
            "link_type",
            "link_value",
            "sort",
            "status",
        )


class StoreNavItemInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=20)
    icon_selected = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    icon_unselected = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    link_type = serializers.ChoiceField(choices=StoreNavItem.LinkType.choices)
    link_value = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(choices=StoreNavItem.Status.choices, required=False, default="ENABLED")


class StoreNavInputSerializer(serializers.Serializer):
    items = StoreNavItemInputSerializer(many=True)


class DecoPageListSerializer(serializers.ModelSerializer):
    component_count = serializers.SerializerMethodField()

    class Meta:
        model = DecoPage
        fields = (
            "id",
            "slug",
            "title",
            "status",
            "component_count",
            "published_at",
            "updated_by_name",
            "updated_at",
        )

    def get_component_count(self, obj) -> int:
        return len(obj.draft_components or [])


class DecoPageSerializer(DecoPageListSerializer):
    class Meta(DecoPageListSerializer.Meta):
        fields = DecoPageListSerializer.Meta.fields + (
            "share_title",
            "share_image",
            "draft_components",
            "published_components",
        )


class DecoPageInputSerializer(serializers.Serializer):
    slug = serializers.CharField(max_length=40)
    title = serializers.CharField(max_length=80)
    share_title = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    share_image = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    draft_components = serializers.ListField(child=serializers.JSONField(), required=False, default=list)


class PublicDecoPageSerializer(serializers.ModelSerializer):
    components = serializers.JSONField(source="published_components", read_only=True)

    class Meta:
        model = DecoPage
        fields = ("slug", "title", "share_title", "share_image", "components", "published_at")
