"""治理接口序列化：操作日志与规则版本。"""

from rest_framework import serializers

from .models import OperationLog, RuleVersion


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
