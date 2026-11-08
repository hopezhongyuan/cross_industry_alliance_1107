"""结算、提现与账单序列化。"""

from rest_framework import serializers

from .models import SettlementBatch, SettlementItem, WithdrawalOrder


class WithdrawalInputSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.IntegerField(required=False, allow_null=True)


class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithdrawalOrder
        fields = (
            "id",
            "withdrawal_no",
            "merchant_id",
            "amount",
            "fee",
            "net_amount",
            "status",
            "requested_at",
            "paid_at",
            "voucher_no",
            "voucher_url",
            "fail_reason",
        )


class PayoutInputSerializer(serializers.Serializer):
    voucher_no = serializers.CharField(max_length=64)
    voucher_url = serializers.URLField(max_length=200)
    paid_at = serializers.DateTimeField()


class RejectInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)


class StatementItemSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source="order.order_no", read_only=True)

    class Meta:
        model = SettlementItem
        fields = (
            "order_no",
            "order_completed_at",
            "due_at",
            "product_amount",
            "delivery_fee",
            "commission_rate",
            "commission_amount",
            "refund_amount",
            "net_amount",
            "status",
        )


class SettlementBatchSerializer(serializers.ModelSerializer):
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SettlementBatch
        fields = (
            "id",
            "batch_no",
            "period_start",
            "period_end",
            "status",
            "total_amount",
            "commission_amount",
            "net_amount",
            "items_count",
            "published_at",
        )


class FreezeInputSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["FREEZE", "UNFREEZE"])
    reason = serializers.CharField(max_length=200)
