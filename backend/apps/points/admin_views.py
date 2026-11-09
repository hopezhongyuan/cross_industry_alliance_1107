"""平台后台积分管理：规则配置、用户积分列表、积分调整。"""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated

from apps.common.api import EnvelopeAPIView, EnvelopeResponse, ok, paginated
from apps.governance.services import log_operation, require_platform_admin

from .models import PointTransaction, UserPointAccount
from .serializers import (
    AdminAdjustInputSerializer,
    PointsConfigInputSerializer,
    PointsConfigSerializer,
    PointTransactionSerializer,
    UserPointAccountSerializer,
)
from .services import adjust_by_admin, get_config


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminPointsConfigView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PointsConfigSerializer

    def get(self, request):
        require_platform_admin(request.user)
        return ok(request, PointsConfigSerializer(get_config()).data)

    def put(self, request):
        require_platform_admin(request.user)
        serializer = PointsConfigInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            config = get_config()
            before = PointsConfigSerializer(config).data
            for key, value in serializer.validated_data.items():
                setattr(config, key, value)
            config.updated_by_name = getattr(request.user, "nickname", "") or getattr(request.user, "phone", "") or ""
            config.save()
        log_operation(
            operator=request.user,
            action="POINTS_CONFIG_UPDATE",
            biz_type="POINTS_CONFIG",
            before=before,
            after=PointsConfigSerializer(config).data,
            request=request,
        )
        return ok(request, PointsConfigSerializer(config).data)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminPointsUserListView(EnvelopeAPIView):
    """用户积分账户列表，可按手机号/昵称搜索。"""

    permission_classes = [IsAuthenticated]
    serializer_class = UserPointAccountSerializer

    def get(self, request):
        require_platform_admin(request.user)
        queryset = UserPointAccount.objects.select_related("user").order_by("-balance", "-id")
        keyword = request.query_params.get("keyword", "").strip()
        if keyword:
            queryset = queryset.filter(user__phone__icontains=keyword) | queryset.filter(
                user__nickname__icontains=keyword
            )
        return ok(request, paginated(request, queryset, UserPointAccountSerializer))


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminPointsUserTransactionView(EnvelopeAPIView):
    """指定用户的积分流水。"""

    permission_classes = [IsAuthenticated]
    serializer_class = PointTransactionSerializer

    def get(self, request, user_id):
        require_platform_admin(request.user)
        queryset = PointTransaction.objects.filter(user_id=user_id).order_by("-created_at")
        return ok(request, paginated(request, queryset, PointTransactionSerializer))


@extend_schema(tags=["admin"], request=AdminAdjustInputSerializer, responses=EnvelopeResponse)
class AdminPointsAdjustView(EnvelopeAPIView):
    """后台人工调整用户积分，可正可负，必填原因。"""

    permission_classes = [IsAuthenticated]
    serializer_class = AdminAdjustInputSerializer

    def post(self, request):
        require_platform_admin(request.user)
        serializer = AdminAdjustInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        operator_name = getattr(request.user, "nickname", "") or getattr(request.user, "phone", "") or ""
        txn = adjust_by_admin(
            user_id=data["user_id"],
            delta=data["delta"],
            reason=data["reason"],
            operator_name=operator_name,
        )
        log_operation(
            operator=request.user,
            action="POINTS_ADJUST",
            biz_type="POINT_TRANSACTION",
            biz_id=txn.id,
            after={"user_id": data["user_id"], "delta": data["delta"], "balance_after": txn.balance_after},
            reason=data["reason"],
            request=request,
        )
        return ok(request, PointTransactionSerializer(txn).data, status_code=201)
