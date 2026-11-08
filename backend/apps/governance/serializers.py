"""治理接口序列化：操作日志、规则版本与审核任务。"""

from rest_framework import serializers

from .models import AuditTask, MediaAsset, MediaFolder, OperationLog, RuleVersion


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
