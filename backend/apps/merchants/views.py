"""消费者端门店浏览与平台端商户管理。"""

import math

from django.db.models import BigIntegerField, Count, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.common.api import ApiError, EnvelopeAPIView, EnvelopeResponse, ok, paginated
from apps.governance.services import require_platform_admin
from apps.ledger.models import SettlementItem
from apps.orders.models import Order

from .models import Merchant
from .serializers import (
    AdminMerchantCreateInputSerializer,
    AdminMerchantDetailSerializer,
    AdminMerchantLocationInputSerializer,
    AdminMerchantSerializer,
    MerchantSerializer,
    MerchantStatusInputSerializer,
    StoreSerializer,
)
from .services import change_merchant_status, create_merchant, update_merchant_location


def _distance_meters(lat1, lng1, lat2, lng2) -> int:
    radius = 6371000
    rad = math.radians
    d_lat = rad(lat2 - lat1)
    d_lng = rad(lng2 - lng1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(d_lng / 2) ** 2
    return int(2 * radius * math.asin(math.sqrt(a)))


class MerchantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Merchant.objects.filter(status=Merchant.Status.ACTIVE).select_related("category").order_by("-created_at")
    serializer_class = MerchantSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    filterset_fields = ("category", "city", "district")
    search_fields = ("name", "short_name")


@extend_schema(tags=["consumer"], responses=EnvelopeResponse)
class StoreNearbyView(EnvelopeAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = StoreSerializer

    def get(self, request):
        lat_value = request.query_params.get("lat")
        lng_value = request.query_params.get("lng")
        if not lat_value or not lng_value:
            raise ApiError("VALIDATION_ERROR", "缺少 lat / lng", 422)
        try:
            lat = float(lat_value)
            lng = float(lng_value)
            radius = int(request.query_params.get("radius", 3000))
        except ValueError:
            raise ApiError("VALIDATION_ERROR", "坐标或半径格式错误", 422) from None

        queryset = Merchant.objects.filter(status=Merchant.Status.ACTIVE).select_related("category")
        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(category_id=category)
        keyword = request.query_params.get("q")
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)

        stores = []
        for merchant in queryset:
            if merchant.lat is not None and merchant.lng is not None:
                distance = _distance_meters(lat, lng, float(merchant.lat), float(merchant.lng))
                if distance > radius:
                    continue
                merchant.distance_meters = distance
            else:
                merchant.distance_meters = None
            stores.append(merchant)
        stores.sort(key=lambda item: (item.distance_meters is None, item.distance_meters or 0, -item.id))

        page = max(int(request.query_params.get("page", 1)), 1)
        size = min(max(int(request.query_params.get("page_size", 20)), 1), 100)
        total = len(stores)
        page_items = stores[(page - 1) * size : page * size]
        return ok(
            request,
            {
                "items": StoreSerializer(page_items, many=True).data,
                "page": {
                    "page": page,
                    "page_size": size,
                    "total": total,
                    "has_more": page * size < total,
                },
            },
        )


@extend_schema(tags=["consumer"], responses=EnvelopeResponse)
class StoreDetailView(EnvelopeAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = StoreSerializer

    def get(self, request, pk):
        merchant = Merchant.objects.filter(pk=pk, status=Merchant.Status.ACTIVE).select_related("category").first()
        if merchant is None:
            raise ApiError("NOT_FOUND", "门店不存在", 404)
        return ok(request, StoreSerializer(merchant).data)


def _admin_merchant_queryset():
    """列表与详情共用的经营统计：今日订单、累计结算、累计 GMV。"""
    today = timezone.localdate()
    today_orders = (
        Order.objects.filter(merchant_id=OuterRef("pk"), created_at__date=today)
        .values("merchant_id")
        .annotate(total=Count("id"))
        .values("total")
    )
    settled = (
        SettlementItem.objects.filter(merchant_id=OuterRef("pk"), status=SettlementItem.Status.SETTLED)
        .values("merchant_id")
        .annotate(total=Sum("net_amount"))
        .values("total")
    )
    gmv = (
        Order.objects.filter(merchant_id=OuterRef("pk"))
        .values("merchant_id")
        .annotate(total=Sum("paid_amount"))
        .values("total")
    )
    return Merchant.objects.select_related("category").annotate(
        today_orders=Coalesce(Subquery(today_orders, output_field=IntegerField()), Value(0)),
        settled_amount=Coalesce(
            Subquery(settled, output_field=BigIntegerField()),
            Value(0, output_field=BigIntegerField()),
        ),
        gmv_total=Coalesce(Subquery(gmv, output_field=BigIntegerField()), Value(0, output_field=BigIntegerField())),
    )


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminMerchantListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminMerchantSerializer

    @extend_schema(operation_id="listAdminMerchants")
    def get(self, request):
        require_platform_admin(request.user)
        queryset = _admin_merchant_queryset().order_by("-created_at", "-id")

        status = request.query_params.get("status")
        if status:
            if status not in Merchant.Status.values:
                raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
            queryset = queryset.filter(status=status)

        keyword = request.query_params.get("q")
        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(short_name__icontains=keyword)
                | Q(merchant_no__icontains=keyword)
                | Q(contact_phone__icontains=keyword)
            )

        category = request.query_params.get("category")
        if category:
            try:
                queryset = queryset.filter(category_id=int(category))
            except ValueError:
                raise ApiError("VALIDATION_ERROR", "category 取值非法", 422) from None

        city = request.query_params.get("city")
        if city:
            queryset = queryset.filter(city__icontains=city)

        payload = paginated(request, queryset, AdminMerchantSerializer)
        payload["summary"] = Merchant.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(status=Merchant.Status.ACTIVE)),
            pending=Count("id", filter=Q(status=Merchant.Status.PENDING)),
            resting=Count("id", filter=Q(status=Merchant.Status.RESTING)),
            banned=Count("id", filter=Q(status=Merchant.Status.BANNED)),
            rejected=Count("id", filter=Q(status=Merchant.Status.REJECTED)),
        )
        return ok(request, payload)

    @extend_schema(
        operation_id="createAdminMerchant",
        request=AdminMerchantCreateInputSerializer,
        responses=EnvelopeResponse,
    )
    def post(self, request):
        serializer = AdminMerchantCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key", "").strip()
        merchant, created = create_merchant(request.user, serializer.validated_data, key, request=request)
        merchant = (
            _admin_merchant_queryset()
            .select_related("account")
            .prefetch_related("qualifications", "staff__user")
            .get(pk=merchant.pk)
        )
        return ok(
            request,
            AdminMerchantDetailSerializer(merchant).data,
            status_code=201 if created else 200,
        )


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminMerchantDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminMerchantDetailSerializer

    @extend_schema(operation_id="getAdminMerchant")
    def get(self, request, pk):
        require_platform_admin(request.user)
        merchant = (
            _admin_merchant_queryset()
            .select_related("account")
            .prefetch_related("qualifications", "staff__user")
            .filter(pk=pk)
            .first()
        )
        if merchant is None:
            raise ApiError("NOT_FOUND", "商户不存在", 404)
        return ok(request, AdminMerchantDetailSerializer(merchant).data)


@extend_schema(
    tags=["admin"],
    request=MerchantStatusInputSerializer,
    responses=EnvelopeResponse,
)
class AdminMerchantStatusView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MerchantStatusInputSerializer

    @extend_schema(operation_id="changeMerchantStatus")
    def post(self, request, pk):
        serializer = MerchantStatusInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        merchant, changed = change_merchant_status(
            request.user,
            pk,
            serializer.validated_data["status"],
            serializer.validated_data["reason"],
            request=request,
        )
        return ok(request, {"id": merchant.id, "status": merchant.status, "changed": changed})


@extend_schema(
    tags=["admin"],
    request=AdminMerchantLocationInputSerializer,
    responses=EnvelopeResponse,
)
class AdminMerchantLocationView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminMerchantLocationInputSerializer

    @extend_schema(operation_id="updateMerchantLocation")
    def put(self, request, pk):
        serializer = AdminMerchantLocationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        merchant = update_merchant_location(request.user, pk, serializer.validated_data, request=request)
        return ok(
            request,
            {
                "id": merchant.id,
                "lng": merchant.lng,
                "lat": merchant.lat,
                "province": merchant.province,
                "city": merchant.city,
                "district": merchant.district,
                "address": merchant.address,
            },
        )
