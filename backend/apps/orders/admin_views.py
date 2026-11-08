"""平台后台订单查询（数据脱敏）。"""

from django.utils.dateparse import parse_date
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated

from apps.common.api import ApiError, EnvelopeAPIView, EnvelopeResponse, ok, paginated
from apps.governance.services import require_platform_admin

from .models import Order
from .serializers import OrderItemSerializer


class AdminOrderListSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_no",
            "merchant_id",
            "merchant_name",
            "order_type",
            "status",
            "payable_amount",
            "paid_amount",
            "refunded_amount",
            "created_at",
            "completed_at",
        )


class AdminOrderDetailSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_no",
            "merchant_id",
            "merchant_name",
            "order_type",
            "status",
            "product_amount",
            "delivery_fee",
            "payable_amount",
            "paid_amount",
            "refunded_amount",
            "commission_rate",
            "commission_amount",
            "platform_income_amount",
            "merchant_income_amount",
            "platform_refund_amount",
            "merchant_refund_amount",
            "created_at",
            "completed_at",
            "items",
        )


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminOrderDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminOrderDetailSerializer

    @extend_schema(operation_id="getAdminOrder")
    def get(self, request, pk):
        require_platform_admin(request.user)
        order = Order.objects.select_related("merchant").prefetch_related("items").filter(pk=pk).first()
        if order is None:
            raise ApiError("NOT_FOUND", "订单不存在", 404)
        return ok(request, AdminOrderDetailSerializer(order).data)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminOrderListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminOrderListSerializer

    def get(self, request):
        require_platform_admin(request.user)
        queryset = Order.objects.select_related("merchant").order_by("-created_at")
        status = request.query_params.get("status")
        if status:
            if status not in set(Order.Status.values):
                raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
            queryset = queryset.filter(status=status)
        merchant_id = request.query_params.get("merchant_id")
        if merchant_id:
            queryset = queryset.filter(merchant_id=merchant_id)
        order_no = request.query_params.get("order_no")
        if order_no:
            queryset = queryset.filter(order_no__icontains=order_no)
        for param, lookup in (("dateFrom", "created_at__date__gte"), ("dateTo", "created_at__date__lte")):
            value = request.query_params.get(param)
            if value:
                parsed = parse_date(value)
                if parsed is None:
                    raise ApiError("VALIDATION_ERROR", f"{param} 日期格式错误", 422)
                queryset = queryset.filter(**{lookup: parsed})
        return ok(request, paginated(request, queryset, AdminOrderListSerializer))
