"""售后请求与响应序列化。"""

from rest_framework import serializers

from apps.payments.models import RefundOrder

from .models import AfterSale, ArbitrationCase


class AfterSaleInputSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    order_item_id = serializers.IntegerField(required=False, allow_null=True)
    type = serializers.ChoiceField(choices=["REFUND_ONLY", "RETURN_REFUND", "SERVICE_ISSUE"])
    reason_code = serializers.CharField(max_length=32)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    evidence = serializers.ListField(child=serializers.URLField(), required=False, allow_empty=True)
    request_amount = serializers.IntegerField(min_value=1)


class AfterSaleDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["AGREE", "REJECT"])
    approved_amount = serializers.IntegerField(min_value=1, required=False)
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class RefundBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundOrder
        fields = ("refund_no", "amount", "status", "refunded_at")


class ArbitrationBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArbitrationCase
        fields = ("case_no", "status", "liability", "ruling", "deadline_at")


class AfterSaleSerializer(serializers.ModelSerializer):
    arbitration = ArbitrationBriefSerializer(read_only=True)
    refunds = RefundBriefSerializer(many=True, read_only=True)

    class Meta:
        model = AfterSale
        fields = (
            "id",
            "after_sale_no",
            "order_id",
            "type",
            "status",
            "request_amount",
            "approved_amount",
            "merchant_decision",
            "merchant_reason",
            "deadline_at",
            "arbitration",
            "refunds",
            "created_at",
            "closed_at",
        )
