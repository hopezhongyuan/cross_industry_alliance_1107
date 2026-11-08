"""售后接口。"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated

from apps.common.api import ApiError, EnvelopeAPIView, EnvelopeResponse, ok, paginated
from apps.governance.services import require_platform_admin

from .models import AfterSale, ArbitrationCase
from .serializers import (
    AfterSaleDecisionSerializer,
    AfterSaleInputSerializer,
    AfterSaleSerializer,
    ArbitrationCaseSerializer,
    ArbitrationRuleInputSerializer,
)
from .services import apply_after_sale, decide_after_sale, rule_arbitration


@extend_schema(tags=["aftersale"], request=AfterSaleInputSerializer, responses=EnvelopeResponse)
class AfterSaleCreateView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AfterSaleInputSerializer

    def post(self, request):
        serializer = AfterSaleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        after_sale = apply_after_sale(request.user, **serializer.validated_data)
        return ok(request, AfterSaleSerializer(after_sale).data, status_code=201)


@extend_schema(tags=["aftersale"], responses=EnvelopeResponse)
class AfterSaleDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AfterSaleSerializer

    def get(self, request, pk):
        after_sale = get_object_or_404(AfterSale, pk=pk, user=request.user)
        return ok(request, AfterSaleSerializer(after_sale).data)


@extend_schema(tags=["merchant"], request=AfterSaleDecisionSerializer, responses=EnvelopeResponse)
class AfterSaleDecisionView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AfterSaleDecisionSerializer

    def post(self, request, pk):
        serializer = AfterSaleDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        after_sale = decide_after_sale(request.user, pk, **serializer.validated_data)
        return ok(request, AfterSaleSerializer(after_sale).data)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminArbitrationListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ArbitrationCaseSerializer

    def get(self, request):
        require_platform_admin(request.user)
        queryset = ArbitrationCase.objects.select_related("after_sale").order_by("-created_at")
        status = request.query_params.get("status")
        if status:
            if status not in set(ArbitrationCase.Status.values):
                raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
            queryset = queryset.filter(status=status)
        return ok(request, paginated(request, queryset, ArbitrationCaseSerializer))


@extend_schema(tags=["admin"], request=ArbitrationRuleInputSerializer, responses=EnvelopeResponse)
class AdminArbitrationRuleView(EnvelopeAPIView):
    """平台仲裁裁定：记录责任方并执行退款（商户/平台承担）。"""

    permission_classes = [IsAuthenticated]
    serializer_class = ArbitrationRuleInputSerializer

    def post(self, request, pk):
        serializer = ArbitrationRuleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        after_sale = rule_arbitration(request.user, pk, **serializer.validated_data)
        return ok(request, AfterSaleSerializer(after_sale).data)
