"""平台后台商品类目、商品管理与模板管理。"""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated

from apps.common.api import ApiError, EnvelopeAPIView, EnvelopeResponse, ok, paginated
from apps.governance.services import log_operation, require_platform_admin

from .merchant_services import admin_batch_set_product_status, admin_set_product_status, admin_update_product
from .models import Category, Product, ProductTemplate
from .serializers import (
    AdminCategoryInputSerializer,
    AdminCategorySerializer,
    AdminProductBatchStatusInputSerializer,
    AdminProductDetailSerializer,
    AdminProductListSerializer,
    AdminProductStatusInputSerializer,
    AdminTemplateInputSerializer,
    AdminTemplateSerializer,
    MerchantProductInputSerializer,
)
from .template_services import create_template, sync_template, update_template


class TemplateSyncInputSerializer(serializers.Serializer):
    merchant_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


def _resolve_parent(parent_id):
    if not parent_id:
        return None
    parent = Category.objects.filter(pk=parent_id).first()
    if parent is None:
        raise ApiError("VALIDATION_ERROR", "父类目不存在", 422)
    if parent.level != 1:
        raise ApiError("VALIDATION_ERROR", "最多支持两级类目", 422)
    return parent


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminCategoryListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminCategorySerializer

    @extend_schema(operation_id="listAdminCategories")
    def get(self, request):
        require_platform_admin(request.user)
        queryset = Category.objects.select_related("parent").order_by("level", "sort", "id")
        parent_id = request.query_params.get("parent")
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        return ok(request, AdminCategorySerializer(queryset, many=True).data)

    @extend_schema(
        operation_id="createAdminCategory",
        request=AdminCategoryInputSerializer,
        responses=EnvelopeResponse,
    )
    def post(self, request):
        require_platform_admin(request.user)
        serializer = AdminCategoryInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent = _resolve_parent(serializer.validated_data.get("parent_id"))
        category = Category.objects.create(
            name=serializer.validated_data["name"],
            parent=parent,
            level=2 if parent else 1,
            icon_url=serializer.validated_data.get("icon_url", ""),
            sort=serializer.validated_data.get("sort", 0),
            status=serializer.validated_data.get("status", Category.Status.ENABLED),
        )
        log_operation(
            operator=request.user,
            action="CATEGORY_CREATE",
            biz_type="CATEGORY",
            biz_id=category.id,
            after={"name": category.name, "level": category.level},
            request=request,
        )
        return ok(request, AdminCategorySerializer(category).data, status_code=201)


@extend_schema(tags=["admin"], request=AdminCategoryInputSerializer, responses=EnvelopeResponse)
class AdminCategoryDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminCategoryInputSerializer

    @extend_schema(operation_id="updateAdminCategory")
    def put(self, request, pk):
        require_platform_admin(request.user)
        serializer = AdminCategoryInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = Category.objects.filter(pk=pk).first()
        if category is None:
            raise ApiError("NOT_FOUND", "类目不存在", 404)
        parent = _resolve_parent(serializer.validated_data.get("parent_id"))
        if parent is not None and category.children.exists():
            raise ApiError("VALIDATION_ERROR", "存在二级类目，不能移动为二级", 422)
        category.name = serializer.validated_data["name"]
        category.parent = parent
        category.level = 2 if parent else 1
        category.icon_url = serializer.validated_data.get("icon_url", "")
        category.sort = serializer.validated_data.get("sort", 0)
        category.status = serializer.validated_data.get("status", Category.Status.ENABLED)
        category.save()
        log_operation(
            operator=request.user,
            action="CATEGORY_UPDATE",
            biz_type="CATEGORY",
            biz_id=category.id,
            after={"name": category.name, "level": category.level, "status": category.status},
            request=request,
        )
        return ok(request, AdminCategorySerializer(category).data)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminProductListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminProductListSerializer

    @extend_schema(operation_id="listAdminProducts")
    def get(self, request):
        require_platform_admin(request.user)
        queryset = Product.objects.select_related("merchant", "category").order_by("-created_at", "-id")
        status = request.query_params.get("status")
        if status:
            if status not in Product.Status.values:
                raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
            queryset = queryset.filter(status=status)
        merchant_id = request.query_params.get("merchant_id")
        if merchant_id:
            queryset = queryset.filter(merchant_id=merchant_id)
        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(category_id=category)
        keyword = request.query_params.get("q")
        if keyword:
            queryset = queryset.filter(title__icontains=keyword)
        return ok(request, paginated(request, queryset, AdminProductListSerializer))


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminProductDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminProductDetailSerializer

    @extend_schema(operation_id="getAdminProduct")
    def get(self, request, pk):
        require_platform_admin(request.user)
        product = Product.objects.select_related("merchant", "category").prefetch_related("skus").filter(pk=pk).first()
        if product is None:
            raise ApiError("NOT_FOUND", "商品不存在", 404)
        return ok(request, AdminProductDetailSerializer(product).data)

    @extend_schema(
        operation_id="updateAdminProduct", request=MerchantProductInputSerializer, responses=EnvelopeResponse
    )
    def put(self, request, pk):
        serializer = MerchantProductInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = admin_update_product(request.user, pk, serializer.validated_data, request=request)
        product = (
            Product.objects.select_related("merchant", "category", "merchant_category")
            .prefetch_related("skus")
            .get(pk=product.pk)
        )
        return ok(request, AdminProductDetailSerializer(product).data)


@extend_schema(tags=["admin"], request=AdminProductStatusInputSerializer, responses=EnvelopeResponse)
class AdminProductStatusView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminProductStatusInputSerializer

    @extend_schema(operation_id="setAdminProductStatus")
    def post(self, request, pk):
        serializer = AdminProductStatusInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = admin_set_product_status(
            request.user,
            pk,
            serializer.validated_data["action"],
            serializer.validated_data.get("reason", ""),
            request=request,
        )
        return ok(request, {"id": product.id, "status": product.status, "off_sale_by": product.off_sale_by})


@extend_schema(tags=["admin"], request=AdminProductBatchStatusInputSerializer, responses=EnvelopeResponse)
class AdminProductBatchStatusView(EnvelopeAPIView):
    """批量违规下架 / 恢复：逐条返回结果，失败项不阻断其他项。"""

    permission_classes = [IsAuthenticated]
    serializer_class = AdminProductBatchStatusInputSerializer

    @extend_schema(operation_id="batchSetAdminProductStatus")
    def post(self, request):
        serializer = AdminProductBatchStatusInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = admin_batch_set_product_status(
            request.user,
            serializer.validated_data["ids"],
            serializer.validated_data["action"],
            serializer.validated_data.get("reason", ""),
            request=request,
        )
        succeeded = sum(1 for item in results if item["ok"])
        return ok(request, {"items": results, "succeeded": succeeded, "failed": len(results) - succeeded})


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminTemplateListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminTemplateSerializer

    @extend_schema(operation_id="listAdminTemplates")
    def get(self, request):
        require_platform_admin(request.user)
        queryset = ProductTemplate.objects.prefetch_related("target_merchants", "adoptions").order_by("-created_at")
        status = request.query_params.get("status")
        if status:
            if status not in ProductTemplate.Status.values:
                raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
            queryset = queryset.filter(status=status)
        return ok(request, paginated(request, queryset, AdminTemplateSerializer))

    @extend_schema(
        operation_id="createAdminTemplate",
        request=AdminTemplateInputSerializer,
        responses=EnvelopeResponse,
    )
    def post(self, request):
        serializer = AdminTemplateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = create_template(request.user, serializer.validated_data, request=request)
        return ok(request, AdminTemplateSerializer(template).data, status_code=201)


@extend_schema(tags=["admin"], request=AdminTemplateInputSerializer, responses=EnvelopeResponse)
class AdminTemplateDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminTemplateInputSerializer

    @extend_schema(operation_id="updateAdminTemplate")
    def put(self, request, pk):
        serializer = AdminTemplateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = update_template(request.user, pk, serializer.validated_data, request=request)
        return ok(request, AdminTemplateSerializer(template).data)


@extend_schema(tags=["admin"], request=TemplateSyncInputSerializer, responses=EnvelopeResponse)
class AdminTemplateSyncView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TemplateSyncInputSerializer

    @extend_schema(operation_id="syncAdminTemplate")
    def post(self, request, pk):
        serializer = TemplateSyncInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        synced = sync_template(request.user, pk, serializer.validated_data.get("merchant_ids") or None, request=request)
        return ok(request, {"template_id": pk, "synced": synced})
