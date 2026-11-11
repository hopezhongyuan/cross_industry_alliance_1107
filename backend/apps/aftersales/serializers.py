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
    request_amount = serializers.IntegerField(
        min_value=1,
        help_text="申请金额（分）。卡券待核销订单必须等于未核销部分金额（实付 × 未核销码数 ÷ 总码数）",
    )


class AfterSaleDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["AGREE", "REJECT"])
    approved_amount = serializers.IntegerField(min_value=1, required=False)
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class ArbitrationRuleInputSerializer(serializers.Serializer):
    ruling = serializers.CharField(max_length=500)
    liability = serializers.ChoiceField(choices=["MERCHANT", "USER", "PLATFORM", "SHARED"])
    refund_amount = serializers.IntegerField(min_value=0, default=0)


class RefundBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundOrder
        fields = ("refund_no", "amount", "status", "refunded_at")


class ArbitrationBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArbitrationCase
        fields = ("case_no", "status", "liability", "ruling", "deadline_at")


class ArbitrationCaseSerializer(serializers.ModelSerializer):
    after_sale_no = serializers.CharField(source="after_sale.after_sale_no", read_only=True)
    order_id = serializers.IntegerField(source="after_sale.order_id", read_only=True)
    merchant_id = serializers.IntegerField(source="after_sale.merchant_id", read_only=True)

    class Meta:
        model = ArbitrationCase
        fields = (
            "id",
            "case_no",
            "after_sale_id",
            "after_sale_no",
            "order_id",
            "merchant_id",
            "amount",
            "status",
            "liability",
            "ruling",
            "deadline_at",
            "decided_at",
            "created_at",
        )


class AdminArbitrationDetailSerializer(ArbitrationCaseSerializer):
    after_sale = serializers.SerializerMethodField()
    decided_by_name = serializers.CharField(read_only=True)

    class Meta(ArbitrationCaseSerializer.Meta):
        fields = ArbitrationCaseSerializer.Meta.fields + ("decided_by_name", "after_sale")

    def get_after_sale(self, obj):
        after_sale = obj.after_sale
        return {
            "id": after_sale.id,
            "after_sale_no": after_sale.after_sale_no,
            "order_id": after_sale.order_id,
            "merchant_id": after_sale.merchant_id,
            "merchant_name": after_sale.merchant.name,
            "user_id": after_sale.user_id,
            "user_name": after_sale.user.nickname or "用户",
            "type": after_sale.type,
            "status": after_sale.status,
            "request_amount": after_sale.request_amount,
            "approved_amount": after_sale.approved_amount,
            "description": after_sale.description,
            "evidence": after_sale.evidence_json,
            "merchant_decision": after_sale.merchant_decision,
            "merchant_reason": after_sale.merchant_reason,
            "deadline_at": after_sale.deadline_at,
            "created_at": after_sale.created_at,
        }


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


class MerchantAfterSaleListSerializer(serializers.ModelSerializer):
    """商户端售后列表行：含订单号与商品摘要，便于列表展示。"""

    order_no = serializers.CharField(source="order.order_no", read_only=True)
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    merchant_decision_label = serializers.CharField(source="get_merchant_decision_display", read_only=True)

    class Meta:
        model = AfterSale
        fields = (
            "id",
            "after_sale_no",
            "order_id",
            "order_no",
            "type",
            "type_label",
            "status",
            "status_label",
            "request_amount",
            "approved_amount",
            "merchant_decision",
            "merchant_decision_label",
            "merchant_reason",
            "deadline_at",
            "created_at",
        )
