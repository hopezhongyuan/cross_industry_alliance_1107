"""治理接口：操作日志、规则版本发布。"""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated

from apps.common.api import EnvelopeAPIView, EnvelopeResponse, ok, paginated

from .models import OperationLog
from .serializers import OperationLogSerializer, RuleVersionInputSerializer, RuleVersionSerializer
from .services import publish_rule_version, require_platform_admin


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
