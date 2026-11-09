"""平台后台优惠券接口：创建平台券、列表、上下架。"""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.api import ApiError, EnvelopeResponse, ok
from apps.governance.services import log_operation, require_platform_admin
from apps.merchants.models import Merchant

from .models import Coupon
from .serializers import CouponCreateInputSerializer, CouponSerializer, CouponStatusActionSerializer


@extend_schema(tags=["admin-coupon"], request=CouponCreateInputSerializer, responses=EnvelopeResponse)
class AdminCouponListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        require_platform_admin(request.user)
        qs = Coupon.objects.filter(type=Coupon.Type.PLATFORM).order_by("-created_at")
        return ok(request, CouponSerializer(qs, many=True).data)

    def post(self, request):
        require_platform_admin(request.user)
        serializer = CouponCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        target_ids = data.pop("target_merchant_ids", [])
        coupon = Coupon.objects.create(
            type=Coupon.Type.PLATFORM, created_by_name=request.user.name or request.user.phone, **data
        )
        if target_ids:
            coupon.target_merchants.set(Merchant.objects.filter(pk__in=target_ids))
        log_operation(
            actor=request.user,
            action="CREATE_PLATFORM_COUPON",
            resource="coupon",
            resource_id=coupon.coupon_no,
            details={"name": coupon.name, "face_value": coupon.face_value},
            request=request,
        )
        return ok(request, CouponSerializer(coupon).data, status_code=201)


@extend_schema(tags=["admin-coupon"], responses=EnvelopeResponse)
class AdminCouponStatusView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CouponStatusActionSerializer

    def post(self, request, coupon_id, action):
        require_platform_admin(request.user)
        coupon = Coupon.objects.filter(pk=coupon_id, type=Coupon.Type.PLATFORM).first()
        if coupon is None:
            raise ApiError("NOT_FOUND", "平台优惠券不存在", 404)
        if action == "pause":
            if coupon.status != Coupon.Status.ACTIVE:
                raise ApiError("ORDER_STATE_CONFLICT", "当前状态不允许暂停", 409)
            coupon.status = Coupon.Status.PAUSED
        elif action == "activate":
            if coupon.status not in (Coupon.Status.DRAFT, Coupon.Status.PAUSED):
                raise ApiError("ORDER_STATE_CONFLICT", "当前状态不允许启用", 409)
            coupon.status = Coupon.Status.ACTIVE
        else:
            raise ApiError("VALIDATION_ERROR", "不支持的操作", 422)
        coupon.save(update_fields=["status", "updated_at"])
        log_operation(
            actor=request.user,
            action=f"{action.upper()}_PLATFORM_COUPON",
            resource="coupon",
            resource_id=coupon.coupon_no,
            request=request,
        )
        return ok(request, CouponSerializer(coupon).data)
