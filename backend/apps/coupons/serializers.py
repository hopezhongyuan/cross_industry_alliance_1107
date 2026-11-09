"""优惠券序列化器。"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Coupon, UserCoupon


class CouponSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    scope_type_label = serializers.CharField(source="get_scope_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)
    remaining_stock = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = (
            "id",
            "coupon_no",
            "name",
            "type",
            "type_label",
            "merchant_id",
            "merchant_name",
            "face_value",
            "min_amount",
            "scope_type",
            "scope_type_label",
            "scope_category_ids",
            "scope_product_ids",
            "total_stock",
            "issued_count",
            "remaining_stock",
            "per_user_limit",
            "valid_from",
            "valid_to",
            "status",
            "status_label",
            "description",
        )

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_remaining_stock(self, obj):
        if obj.total_stock == 0:
            return None
        return max(0, obj.total_stock - obj.issued_count)


class CouponCreateInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    face_value = serializers.IntegerField(min_value=1)
    min_amount = serializers.IntegerField(min_value=0, default=0)
    scope_type = serializers.ChoiceField(choices=["ALL", "CATEGORY", "PRODUCT"], default="ALL")
    scope_category_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    scope_product_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    target_merchant_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    total_stock = serializers.IntegerField(min_value=0, default=0)
    per_user_limit = serializers.IntegerField(min_value=0, default=1)
    valid_from = serializers.DateTimeField()
    valid_to = serializers.DateTimeField()
    description = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class CouponStatusActionSerializer(serializers.Serializer):
    """上下架操作无请求体，仅用于 OpenAPI 契约解析。"""

    pass


class UserCouponSerializer(serializers.ModelSerializer):
    coupon = CouponSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = UserCoupon
        fields = (
            "id",
            "user_coupon_no",
            "coupon",
            "status",
            "status_label",
            "expire_at",
            "used_at",
            "order_no",
        )
