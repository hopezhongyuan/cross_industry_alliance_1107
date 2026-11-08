"""商户中心商品管理：发布、编辑、列表与上下架。"""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated

from apps.common.api import ApiError, EnvelopeAPIView, EnvelopeResponse, ok, paginated
from apps.merchants.services import get_active_staff_merchant

from .merchant_services import (
    create_merchant_category,
    create_merchant_product,
    delete_merchant_category,
    set_product_sale_status,
    update_merchant_category,
    update_merchant_product,
)
from .models import MerchantProductCategory, Product
from .serializers import (
    MerchantProductCategoryInputSerializer,
    MerchantProductCategorySerializer,
    MerchantProductDetailSerializer,
    MerchantProductInputSerializer,
    MerchantProductListSerializer,
    MerchantTemplateSerializer,
)
from .template_services import adopt_template, visible_templates


class MerchantProductStatusInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=(Product.Status.ON_SALE, Product.Status.OFF_SALE))


class MerchantTemplateAdoptInputSerializer(serializers.Serializer):
    listed = serializers.BooleanField(required=False, default=True)


@extend_schema(tags=["merchant"], responses=EnvelopeResponse)
class MerchantProductListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MerchantProductListSerializer

    @extend_schema(operation_id="listMerchantProducts")
    def get(self, request):
        merchant = get_active_staff_merchant(request.user)
        queryset = (
            Product.objects.filter(merchant=merchant)
            .select_related("merchant_category")
            .prefetch_related("skus")
            .order_by("-created_at", "-id")
        )
        status = request.query_params.get("status")
        if status:
            if status not in Product.Status.values:
                raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
            queryset = queryset.filter(status=status)
        keyword = request.query_params.get("q")
        if keyword:
            queryset = queryset.filter(title__icontains=keyword)
        return ok(request, paginated(request, queryset, MerchantProductListSerializer))

    @extend_schema(
        operation_id="createMerchantProduct",
        request=MerchantProductInputSerializer,
        responses=EnvelopeResponse,
    )
    def post(self, request):
        serializer = MerchantProductInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = request.headers.get("Idempotency-Key", "").strip()
        product, created = create_merchant_product(request.user, serializer.validated_data, key, request=request)
        return ok(
            request,
            MerchantProductDetailSerializer(product).data,
            status_code=201 if created else 200,
        )


@extend_schema(tags=["merchant"], responses=EnvelopeResponse)
class MerchantProductDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MerchantProductDetailSerializer

    @extend_schema(operation_id="getMerchantProduct")
    def get(self, request, pk):
        merchant = get_active_staff_merchant(request.user)
        product = (
            Product.objects.filter(pk=pk, merchant=merchant)
            .select_related("category", "merchant_category")
            .prefetch_related("skus")
            .first()
        )
        if product is None:
            raise ApiError("NOT_FOUND", "商品不存在", 404)
        return ok(request, MerchantProductDetailSerializer(product).data)

    @extend_schema(
        operation_id="updateMerchantProduct", request=MerchantProductInputSerializer, responses=EnvelopeResponse
    )
    def put(self, request, pk):
        serializer = MerchantProductInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = update_merchant_product(request.user, pk, serializer.validated_data, request=request)
        product = (
            Product.objects.select_related("category", "merchant_category").prefetch_related("skus").get(pk=product.pk)
        )
        return ok(request, MerchantProductDetailSerializer(product).data)


@extend_schema(tags=["merchant"], request=MerchantProductStatusInputSerializer, responses=EnvelopeResponse)
class MerchantProductStatusView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MerchantProductStatusInputSerializer

    @extend_schema(operation_id="setMerchantProductSaleStatus")
    def post(self, request, pk):
        serializer = MerchantProductStatusInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = set_product_sale_status(request.user, pk, serializer.validated_data["status"], request=request)
        return ok(request, {"id": product.id, "status": product.status, "version": product.version})


@extend_schema(tags=["merchant"], responses=EnvelopeResponse)
class MerchantProductCategoryListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MerchantProductCategorySerializer

    @extend_schema(operation_id="listMerchantProductCategories")
    def get(self, request):
        merchant = get_active_staff_merchant(request.user)
        queryset = MerchantProductCategory.objects.filter(merchant=merchant).prefetch_related("products")
        return ok(request, MerchantProductCategorySerializer(queryset, many=True).data)

    @extend_schema(
        operation_id="createMerchantProductCategory",
        request=MerchantProductCategoryInputSerializer,
        responses=EnvelopeResponse,
    )
    def post(self, request):
        serializer = MerchantProductCategoryInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = create_merchant_category(request.user, serializer.validated_data, request=request)
        return ok(request, MerchantProductCategorySerializer(category).data, status_code=201)


@extend_schema(tags=["merchant"], request=MerchantProductCategoryInputSerializer, responses=EnvelopeResponse)
class MerchantProductCategoryDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MerchantProductCategoryInputSerializer

    @extend_schema(operation_id="updateMerchantProductCategory")
    def put(self, request, pk):
        serializer = MerchantProductCategoryInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = update_merchant_category(request.user, pk, serializer.validated_data, request=request)
        return ok(request, MerchantProductCategorySerializer(category).data)

    @extend_schema(operation_id="deleteMerchantProductCategory", responses={204: None})
    def delete(self, request, pk):
        delete_merchant_category(request.user, pk, request=request)
        return ok(request, None, status_code=204)


@extend_schema(tags=["merchant"], responses=EnvelopeResponse)
class MerchantTemplateListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MerchantTemplateSerializer

    @extend_schema(operation_id="listMerchantTemplates")
    def get(self, request):
        merchant = get_active_staff_merchant(request.user)
        queryset = visible_templates(merchant).prefetch_related("adoptions", "category")
        return ok(request, MerchantTemplateSerializer(queryset, many=True, context={"merchant": merchant}).data)


@extend_schema(tags=["merchant"], request=MerchantTemplateAdoptInputSerializer, responses=EnvelopeResponse)
class MerchantTemplateAdoptView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MerchantTemplateAdoptInputSerializer

    @extend_schema(operation_id="adoptMerchantTemplate")
    def post(self, request, pk):
        serializer = MerchantTemplateAdoptInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product, created = adopt_template(
            request.user, pk, serializer.validated_data.get("listed", True), request=request
        )
        return ok(
            request,
            {"product_id": product.id, "status": product.status},
            status_code=201 if created else 200,
        )
