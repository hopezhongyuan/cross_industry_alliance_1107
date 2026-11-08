"""支付回调请求与响应结构（仅用于契约描述）。"""

from rest_framework import serializers

from .models import PlatformPaymentConfig


class CallbackPayloadSerializer(serializers.Serializer):
    payment_no = serializers.CharField()
    transaction_id = serializers.CharField()
    amount = serializers.IntegerField()
    trade_state = serializers.CharField()


class CallbackAckSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()


class PaymentConfigSerializer(serializers.ModelSerializer):
    """响应不含密钥与证书，只返回可公开的配置项。"""

    class Meta:
        model = PlatformPaymentConfig
        fields = (
            "channel",
            "merchant_no",
            "app_id",
            "cert_serial_no",
            "notify_url",
            "enabled",
            "updated_by_name",
            "updated_at",
        )


class PaymentConfigInputSerializer(serializers.Serializer):
    merchant_no = serializers.CharField(max_length=32)
    api_v3_key = serializers.CharField(max_length=64, write_only=True)
    private_key = serializers.CharField(write_only=True)
    platform_cert = serializers.CharField(write_only=True)
    app_id = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    cert_serial_no = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    notify_url = serializers.URLField(required=False, allow_blank=True, default="")
    enabled = serializers.BooleanField(default=False)
