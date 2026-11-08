"""治理接口：操作日志、规则版本、审核中心与素材库。"""

from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from apps.common.api import ApiError, EnvelopeAPIView, EnvelopeResponse, ok, paginated

from .media_services import asset_reference_count, validate_upload
from .models import AuditTask, MediaAsset, MediaFolder, OperationLog
from .serializers import (
    AuditDecisionInputSerializer,
    AuditTaskSerializer,
    MediaAssetSerializer,
    MediaAssetUploadSerializer,
    MediaFolderInputSerializer,
    MediaFolderSerializer,
    OperationLogSerializer,
    RuleVersionInputSerializer,
    RuleVersionSerializer,
)
from .services import decide_audit, publish_rule_version, require_platform_admin


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
