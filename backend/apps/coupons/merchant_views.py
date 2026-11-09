"""商户中心优惠券接口：创建商户券、列表、上下架。"""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.api import ApiError, EnvelopeResponse, ok
from apps.merchants.services import get_active_staff_merchant

from .models import Coupon
from .serializers import CouponCreateInputSerializer, CouponSerializer, CouponStatusActionSerializer


@extend_schema(tags=["merchant-coupon"], request=CouponCreateInputSerializer, responses=EnvelopeResponse)
class MerchantCouponListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        merchant = get_active_staff_merchant(request.user)
        qs = Coupon.objects.filter(type=Coupon.Type.MERCHANT, merchant=merchant).order_by("-created_at")
        return ok(request, CouponSerializer(qs, many=True).data)

    def post(self, request):
        merchant = get_active_staff_merchant(request.user)
        serializer = CouponCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("target_merchant_ids", None)  # 商户券不支持指定参加商户
        coupon = Coupon.objects.create(
            type=Coupon.Type.MERCHANT,
            merchant=merchant,
            created_by_name=request.user.name or request.user.phone,
            **data,
        )
        return ok(request, CouponSerializer(coupon).data, status_code=201)


@extend_schema(tags=["merchant-coupon"], responses=EnvelopeResponse)
class MerchantCouponStatusView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CouponStatusActionSerializer

    def post(self, request, coupon_id, action):
        merchant = get_active_staff_merchant(request.user)
        coupon = Coupon.objects.filter(pk=coupon_id, type=Coupon.Type.MERCHANT, merchant=merchant).first()
        if coupon is None:
            raise ApiError("NOT_FOUND", "商户优惠券不存在", 404)
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
        return ok(request, CouponSerializer(coupon).data)
