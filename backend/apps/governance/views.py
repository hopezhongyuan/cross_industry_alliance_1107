"""治理接口：操作日志、规则版本、审核中心与素材库。"""

from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.common.api import ApiError, EnvelopeAPIView, EnvelopeResponse, ok, paginated

from .media_services import asset_reference_count, validate_upload
from .models import AuditTask, DecoPage, MediaAsset, MediaFolder, OperationLog, StoreNavItem
from .serializers import (
    AdminPlatformConfigInputSerializer,
    AdminPlatformConfigSerializer,
    AuditDecisionInputSerializer,
    AuditTaskSerializer,
    DecoPageInputSerializer,
    DecoPageListSerializer,
    DecoPageSerializer,
    MediaAssetSerializer,
    MediaAssetUploadSerializer,
    MediaFolderInputSerializer,
    MediaFolderSerializer,
    OperationLogSerializer,
    PublicDecoPageSerializer,
    PublicPlatformConfigSerializer,
    RuleVersionInputSerializer,
    RuleVersionSerializer,
    StoreNavInputSerializer,
    StoreNavItemSerializer,
)
from .services import (
    decide_audit,
    get_platform_config,
    publish_rule_version,
    require_platform_admin,
    update_platform_config,
)
from .storefront_services import (
    create_page,
    delete_page,
    public_nav,
    public_page,
    publish_page,
    replace_nav_items,
    update_page,
)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminOperationLogListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OperationLogSerializer

    def get(self, request):
        require_platform_admin(request.user)
        queryset = OperationLog.objects.all().order_by("-created_at", "-id")
        biz_type = request.query_params.get("biz_type")
        if biz_type:
            queryset = queryset.filter(biz_type=biz_type)
        operator = request.query_params.get("operator")
        if operator:
            queryset = queryset.filter(operator_name__icontains=operator)
        biz_id = request.query_params.get("biz_id")
        if biz_id:
            try:
                queryset = queryset.filter(biz_id=int(biz_id))
            except ValueError:
                queryset = queryset.none()
        return ok(request, paginated(request, queryset, OperationLogSerializer))


@extend_schema(tags=["admin"], request=RuleVersionInputSerializer, responses=EnvelopeResponse)
class AdminRulePublishView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RuleVersionInputSerializer

    def put(self, request):
        serializer = RuleVersionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = publish_rule_version(
            request.user,
            snapshot=serializer.validated_data["snapshot"],
            effective_at=serializer.validated_data.get("effective_at"),
            remark=serializer.validated_data.get("remark", ""),
        )
        return ok(request, RuleVersionSerializer(version).data)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminAuditListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AuditTaskSerializer

    @extend_schema(operation_id="listAudits")
    def get(self, request):
        require_platform_admin(request.user)
        queryset = AuditTask.objects.all().order_by("-created_at", "-id")
        biz_type = request.query_params.get("biz_type")
        if biz_type:
            if biz_type not in AuditTask.BizType.values:
                raise ApiError("VALIDATION_ERROR", "biz_type 取值非法", 422)
            queryset = queryset.filter(biz_type=biz_type)
        status = request.query_params.get("status")
        if status:
            if status not in AuditTask.Status.values:
                raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
            queryset = queryset.filter(status=status)

        payload = paginated(request, queryset, AuditTaskSerializer)
        payload["summary"] = {
            row["biz_type"]: row["count"]
            for row in AuditTask.objects.filter(status=AuditTask.Status.PENDING)
            .values("biz_type")
            .annotate(count=Count("id"))
        }
        return ok(request, payload)


@extend_schema(tags=["admin"], request=AuditDecisionInputSerializer, responses=EnvelopeResponse)
class AdminAuditDecisionView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AuditDecisionInputSerializer

    @extend_schema(operation_id="decideAudit")
    def post(self, request, pk):
        serializer = AuditDecisionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = decide_audit(
            request.user,
            pk,
            serializer.validated_data["decision"],
            serializer.validated_data.get("reason", ""),
            request=request,
        )
        return ok(request, AuditTaskSerializer(task).data)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminMediaFolderListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MediaFolderSerializer

    @extend_schema(operation_id="listMediaFolders")
    def get(self, request):
        require_platform_admin(request.user)
        queryset = MediaFolder.objects.prefetch_related("assets").order_by("sort", "id")
        return ok(request, MediaFolderSerializer(queryset, many=True).data)

    @extend_schema(
        operation_id="createMediaFolder",
        request=MediaFolderInputSerializer,
        responses=EnvelopeResponse,
    )
    def post(self, request):
        require_platform_admin(request.user)
        serializer = MediaFolderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"].strip()
        if MediaFolder.objects.filter(name=name).exists():
            raise ApiError("VALIDATION_ERROR", "文件夹名称已存在", 422)
        folder = MediaFolder.objects.create(
            name=name,
            sort=serializer.validated_data.get("sort", 0),
            created_by_name=getattr(request.user, "nickname", "") or getattr(request.user, "phone", ""),
        )
        return ok(request, MediaFolderSerializer(folder).data, status_code=201)


@extend_schema(tags=["admin"], request=MediaFolderInputSerializer, responses=EnvelopeResponse)
class AdminMediaFolderDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MediaFolderInputSerializer

    @extend_schema(operation_id="updateMediaFolder")
    def put(self, request, pk):
        require_platform_admin(request.user)
        serializer = MediaFolderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        folder = MediaFolder.objects.filter(pk=pk).first()
        if folder is None:
            raise ApiError("NOT_FOUND", "文件夹不存在", 404)
        name = serializer.validated_data["name"].strip()
        if MediaFolder.objects.filter(name=name).exclude(pk=folder.pk).exists():
            raise ApiError("VALIDATION_ERROR", "文件夹名称已存在", 422)
        folder.name = name
        folder.sort = serializer.validated_data.get("sort", folder.sort)
        folder.save(update_fields=["name", "sort", "updated_at"])
        return ok(request, MediaFolderSerializer(folder).data)

    @extend_schema(operation_id="deleteMediaFolder", responses={204: None})
    def delete(self, request, pk):
        require_platform_admin(request.user)
        folder = MediaFolder.objects.filter(pk=pk).first()
        if folder is None:
            raise ApiError("NOT_FOUND", "文件夹不存在", 404)
        if folder.assets.exists():
            raise ApiError("VALIDATION_ERROR", "文件夹内仍有素材，不能删除", 409)
        folder.delete()
        return ok(request, None, status_code=204)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminMediaAssetListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MediaAssetSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(operation_id="listMediaAssets")
    def get(self, request):
        require_platform_admin(request.user)
        queryset = MediaAsset.objects.select_related("folder").order_by("-created_at", "-id")
        folder = request.query_params.get("folder")
        if folder:
            if folder == "none":
                queryset = queryset.filter(folder__isnull=True)
            else:
                queryset = queryset.filter(folder_id=folder)
        kind = request.query_params.get("kind")
        if kind:
            if kind not in MediaAsset.Kind.values:
                raise ApiError("VALIDATION_ERROR", "kind 取值非法", 422)
            queryset = queryset.filter(kind=kind)
        keyword = request.query_params.get("q")
        if keyword:
            queryset = queryset.filter(name__icontains=keyword)
        return ok(request, paginated(request, queryset, MediaAssetSerializer))

    @extend_schema(
        operation_id="uploadMediaAsset",
        request=MediaAssetUploadSerializer,
        responses=EnvelopeResponse,
    )
    def post(self, request):
        require_platform_admin(request.user)
        serializer = MediaAssetUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file = serializer.validated_data["file"]
        kind = validate_upload(file)
        folder = None
        folder_id = serializer.validated_data.get("folder_id")
        if folder_id:
            folder = MediaFolder.objects.filter(pk=folder_id).first()
            if folder is None:
                raise ApiError("VALIDATION_ERROR", "文件夹不存在", 422)
        asset = MediaAsset.objects.create(
            folder=folder,
            kind=kind,
            file=file,
            name=serializer.validated_data.get("name", "") or file.name,
            original_name=file.name,
            mime=getattr(file, "content_type", "") or "",
            size=file.size,
            created_by_name=getattr(request.user, "nickname", "") or getattr(request.user, "phone", ""),
        )
        return ok(request, MediaAssetSerializer(asset).data, status_code=201)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminMediaAssetDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MediaAssetSerializer

    @extend_schema(operation_id="deleteMediaAsset", responses={204: None})
    def delete(self, request, pk):
        require_platform_admin(request.user)
        asset = MediaAsset.objects.filter(pk=pk).first()
        if asset is None:
            raise ApiError("NOT_FOUND", "素材不存在", 404)
        if asset_reference_count(asset) > 0:
            raise ApiError("VALIDATION_ERROR", "素材已被业务引用，不能删除", 409)
        asset.file.delete(save=False)
        asset.delete()
        return ok(request, None, status_code=204)


@extend_schema(tags=["admin"], request=AdminPlatformConfigInputSerializer, responses=EnvelopeResponse)
class AdminPlatformConfigView(EnvelopeAPIView):
    """平台配置读写：读取不回显密钥，写入留空表示保持原值。"""

    permission_classes = [IsAuthenticated]
    serializer_class = AdminPlatformConfigInputSerializer

    @extend_schema(operation_id="getAdminPlatformConfig")
    def get(self, request):
        require_platform_admin(request.user)
        config = get_platform_config()
        return ok(request, AdminPlatformConfigSerializer(config).data)

    @extend_schema(operation_id="updateAdminPlatformConfig")
    def put(self, request):
        serializer = AdminPlatformConfigInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = update_platform_config(request.user, serializer.validated_data, request=request)
        return ok(request, AdminPlatformConfigSerializer(config).data)


@extend_schema(tags=["platform"], responses=EnvelopeResponse)
class PublicPlatformConfigView(EnvelopeAPIView):
    """公开平台信息：不含任何密钥明文，供 H5 展示平台名称、协议与地图参数。"""

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PublicPlatformConfigSerializer

    @extend_schema(operation_id="getPlatformConfig")
    def get(self, request):
        config = get_platform_config()
        return ok(request, PublicPlatformConfigSerializer(config).data)


@extend_schema(tags=["admin"], request=StoreNavInputSerializer, responses=EnvelopeResponse)
class AdminStoreNavView(EnvelopeAPIView):
    """平台底部导航：整表替换，最多 5 项。"""

    permission_classes = [IsAuthenticated]
    serializer_class = StoreNavInputSerializer

    @extend_schema(operation_id="getAdminStoreNav")
    def get(self, request):
        require_platform_admin(request.user)
        items = StoreNavItem.objects.all().order_by("sort", "id")
        return ok(request, StoreNavItemSerializer(items, many=True).data)

    @extend_schema(operation_id="updateAdminStoreNav")
    def put(self, request):
        serializer = StoreNavInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = replace_nav_items(request.user, serializer.validated_data["items"], request=request)
        return ok(request, StoreNavItemSerializer(items, many=True).data)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminDecoPageListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DecoPageListSerializer

    @extend_schema(operation_id="listAdminDecoPages")
    def get(self, request):
        require_platform_admin(request.user)
        queryset = DecoPage.objects.all()
        status = request.query_params.get("status")
        if status:
            if status not in DecoPage.Status.values:
                raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
            queryset = queryset.filter(status=status)
        return ok(request, paginated(request, queryset, DecoPageListSerializer))

    @extend_schema(
        operation_id="createAdminDecoPage",
        request=DecoPageInputSerializer,
        responses=EnvelopeResponse,
    )
    def post(self, request):
        serializer = DecoPageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        page = create_page(request.user, serializer.validated_data, request=request)
        return ok(request, DecoPageSerializer(page).data, status_code=201)


@extend_schema(tags=["admin"], request=DecoPageInputSerializer, responses=EnvelopeResponse)
class AdminDecoPageDetailView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DecoPageInputSerializer

    @extend_schema(operation_id="getAdminDecoPage")
    def get(self, request, pk):
        require_platform_admin(request.user)
        page = DecoPage.objects.filter(pk=pk).first()
        if page is None:
            raise ApiError("NOT_FOUND", "微页面不存在", 404)
        return ok(request, DecoPageSerializer(page).data)

    @extend_schema(operation_id="updateAdminDecoPage")
    def put(self, request, pk):
        serializer = DecoPageInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        page = update_page(request.user, pk, serializer.validated_data, request=request)
        return ok(request, DecoPageSerializer(page).data)

    @extend_schema(operation_id="deleteAdminDecoPage", responses={204: None})
    def delete(self, request, pk):
        delete_page(request.user, pk, request=request)
        return ok(request, None, status_code=204)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminDecoPagePublishView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DecoPageInputSerializer

    @extend_schema(operation_id="publishAdminDecoPage")
    def post(self, request, pk):
        page = publish_page(request.user, pk, request=request)
        return ok(request, DecoPageSerializer(page).data)


@extend_schema(tags=["storefront"], responses=EnvelopeResponse)
class PublicStoreNavView(EnvelopeAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = StoreNavItemSerializer

    @extend_schema(operation_id="getStoreNav")
    def get(self, request):
        return ok(request, StoreNavItemSerializer(public_nav(), many=True).data)


@extend_schema(tags=["storefront"], responses=EnvelopeResponse)
class PublicDecoPageView(EnvelopeAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = PublicDecoPageSerializer

    @extend_schema(operation_id="getDecoPage")
    def get(self, request, slug):
        page = public_page(slug)
        if page is None:
            raise ApiError("NOT_FOUND", "微页面不存在或未发布", 404)
        return ok(request, PublicDecoPageSerializer(page).data)
