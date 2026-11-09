"""积分序列化器。"""

from rest_framework import serializers

from .models import PointsConfig, PointTransaction, UserPointAccount


class PointsConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointsConfig
        fields = (
            "enabled",
            "consumption_rate",
            "consumption_max_per_order",
            "signin_points",
            "share_points",
            "share_daily_limit",
            "register_points",
            "review_points",
            "updated_by_name",
        )


class PointsConfigInputSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False)
    consumption_rate = serializers.IntegerField(min_value=1, required=False)
    consumption_max_per_order = serializers.IntegerField(min_value=0, required=False)
    signin_points = serializers.IntegerField(min_value=0, required=False)
    share_points = serializers.IntegerField(min_value=0, required=False)
    share_daily_limit = serializers.IntegerField(min_value=0, required=False)
    register_points = serializers.IntegerField(min_value=0, required=False)
    review_points = serializers.IntegerField(min_value=0, required=False)


class UserPointAccountSerializer(serializers.ModelSerializer):
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    user_nickname = serializers.CharField(source="user.nickname", read_only=True)

    class Meta:
        model = UserPointAccount
        fields = ("id", "user_id", "user_phone", "user_nickname", "balance", "total_earned", "total_spent")


class PointTransactionSerializer(serializers.ModelSerializer):
    biz_type_label = serializers.CharField(source="get_biz_type_display", read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = PointTransaction
        fields = (
            "id",
            "user_id",
            "biz_type",
            "biz_type_label",
            "delta",
            "balance_after",
            "biz_id",
            "remark",
            "operator_name",
            "created_at",
        )


class ShareInputSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=["PRODUCT", "MERCHANT", "PAGE"])
    target_id = serializers.IntegerField(min_value=1)


class AdminAdjustInputSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    delta = serializers.IntegerField()
    reason = serializers.CharField(max_length=200)
