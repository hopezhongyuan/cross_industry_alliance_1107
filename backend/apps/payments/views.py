"""微信支付回调入口（M1 Mock）。"""

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api import ApiError, EnvelopeAPIView, EnvelopeResponse, ok
from apps.governance.services import require_platform_admin
from apps.orders.serializers import PayInputSerializer

from .models import PaymentOrder, PlatformPaymentConfig
from .serializers import (
    CallbackAckSerializer,
    CallbackPayloadSerializer,
    PaymentConfigInputSerializer,
    PaymentConfigSerializer,
)
from .services import (
    create_group_payment,
    process_group_payment_success,
    process_payment_success,
    upsert_payment_config,
)


@extend_schema(request=CallbackPayloadSerializer, responses={200: CallbackAckSerializer})
class WechatPayCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = CallbackAckSerializer

    def post(self, request):
        if not settings.WECHAT_MOCK_MODE:
            return Response({"code": "FAIL", "message": "真实微信回调未接入（M5）"}, status=503)
        try:
            payment_no = str(request.data.get("payment_no", ""))[:32]
            transaction_id = str(request.data.get("transaction_id", ""))[:64]
            amount = int(request.data.get("amount", 0))
            if request.data.get("trade_state") != "SUCCESS":
                raise ApiError("PAYMENT_NOT_SUCCESS", "支付未成功", 400)
            if not payment_no or not transaction_id:
                raise ApiError("VALIDATION_ERROR", "缺少支付单号或交易号", 400)
            if payment_no.startswith("G"):
                process_group_payment_success(payment_no, transaction_id, amount)
            else:
                process_payment_success(payment_no, transaction_id, amount)
        except ApiError as exc:
            return Response({"code": "FAIL", "message": exc.message}, status=exc.status_code)
        except (TypeError, ValueError):
            return Response({"code": "FAIL", "message": "回调参数格式错误"}, status=400)
        return Response({"code": "SUCCESS", "message": "ok"})


@extend_schema(tags=["payment"], request=PayInputSerializer, responses=EnvelopeResponse)
class GroupPayView(EnvelopeAPIView):
    """合单支付：为跨商户订单组发起一笔支付。"""

    permission_classes = [IsAuthenticated]
    serializer_class = PayInputSerializer

    def post(self, request, group_no):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            raise ApiError("VALIDATION_ERROR", "缺少 Idempotency-Key", 422)
        serializer = PayInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group, pay_params = create_group_payment(
            request.user, group_no, serializer.validated_data["channel"], idempotency_key
        )
        return ok(
            request,
            {
                "group_no": group.group_no,
                "prepay_id": group.prepay_id,
                "pay_params": pay_params,
                "expire_at": group.expire_at.isoformat() if group.expire_at else None,
            },
        )


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class PaymentConfigView(EnvelopeAPIView):
    """平台支付配置读写：读取不含密钥，写入加密存储。"""

    permission_classes = [IsAuthenticated]
    serializer_class = PaymentConfigSerializer

    def get(self, request, channel):
        require_platform_admin(request.user)
        config = PlatformPaymentConfig.objects.filter(channel=channel).first()
        if config is None:
            raise ApiError("NOT_FOUND", "支付配置不存在", 404)
        return ok(request, PaymentConfigSerializer(config).data)

    @extend_schema(request=PaymentConfigInputSerializer, responses=EnvelopeResponse)
    def put(self, request, channel):
        require_platform_admin(request.user)
        if channel not in PaymentOrder.Channel.values:
            raise ApiError("VALIDATION_ERROR", "不支持的支付渠道", 422)
        serializer = PaymentConfigInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = upsert_payment_config(request.user, channel, request=request, **serializer.validated_data)
        return ok(request, PaymentConfigSerializer(config).data)
