"""消费者端积分接口。"""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated

from apps.common.api import EnvelopeAPIView, EnvelopeResponse, ok, paginated

from .models import PointTransaction
from .serializers import (
    PointsConfigSerializer,
    PointTransactionSerializer,
    ShareInputSerializer,
    UserPointAccountSerializer,
)
from .services import get_config, get_or_create_account, share, signin


@extend_schema(tags=["consumer"], responses=EnvelopeResponse)
class PointAccountView(EnvelopeAPIView):
    """当前用户积分账户：余额、累计获得、累计消耗。"""

    permission_classes = [IsAuthenticated]
    serializer_class = UserPointAccountSerializer

    def get(self, request):
        account = get_or_create_account(request.user.id)
        return ok(request, UserPointAccountSerializer(account).data)


@extend_schema(tags=["consumer"], responses=EnvelopeResponse)
class PointTransactionListView(EnvelopeAPIView):
    """当前用户积分流水，可按 biz_type 过滤。"""

    permission_classes = [IsAuthenticated]
    serializer_class = PointTransactionSerializer

    def get(self, request):
        queryset = PointTransaction.objects.filter(user=request.user).order_by("-created_at")
        biz_type = request.query_params.get("biz_type")
        if biz_type:
            if biz_type not in set(PointTransaction.BizType.values):
                from apps.common.api import ApiError

                raise ApiError("VALIDATION_ERROR", "biz_type 取值非法", 422)
            queryset = queryset.filter(biz_type=biz_type)
        return ok(request, paginated(request, queryset, PointTransactionSerializer))


@extend_schema(tags=["consumer"], responses=EnvelopeResponse)
class PointSigninView(EnvelopeAPIView):
    """签到；每日一次，重复调用幂等。"""

    permission_classes = [IsAuthenticated]
    serializer_class = PointTransactionSerializer

    def post(self, request):
        txn = signin(request.user.id)
        return ok(request, {"delta": txn.delta, "balance_after": txn.balance_after})


@extend_schema(tags=["consumer"], request=ShareInputSerializer, responses=EnvelopeResponse)
class PointShareView(EnvelopeAPIView):
    """分享赚积分；每日次数上限内发放，超出返回 awarded=False。"""

    permission_classes = [IsAuthenticated]
    serializer_class = ShareInputSerializer

    def post(self, request):
        serializer = ShareInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        txn = share(request.user.id, serializer.validated_data["target_type"], serializer.validated_data["target_id"])
        if txn is None:
            return ok(
                request, {"awarded": False, "delta": 0, "balance_after": get_or_create_account(request.user.id).balance}
            )
        return ok(request, {"awarded": True, "delta": txn.delta, "balance_after": txn.balance_after})


@extend_schema(tags=["consumer"], responses=EnvelopeResponse)
class PointRulesView(EnvelopeAPIView):
    """公开积分规则（供前端展示）。"""

    permission_classes = []
    authentication_classes = []
    serializer_class = PointsConfigSerializer

    def get(self, request):
        return ok(request, PointsConfigSerializer(get_config()).data)
