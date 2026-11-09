"""消费者端优惠券接口：领券中心、我的券、可用券、领取。"""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.api import EnvelopeAPIView, EnvelopeResponse, ok

from .models import Coupon
from .serializers import CouponSerializer, UserCouponSerializer
from .services import claim_coupon, get_available_coupons


@extend_schema(tags=["coupon"], responses=EnvelopeResponse)
class CouponCenterView(APIView):
    """领券中心：平台券 + 指定商户券。"""

    permission_classes = [IsAuthenticated]
    serializer_class = CouponSerializer

    def get(self, request):
        from django.utils import timezone

        now = timezone.now()
        merchant_id = request.query_params.get("merchant_id")
        qs = Coupon.objects.filter(status=Coupon.Status.ACTIVE, valid_from__lte=now, valid_to__gt=now)
        platform = list(qs.filter(type=Coupon.Type.PLATFORM))
        result = platform
        if merchant_id:
            merchant_coupons = list(qs.filter(type=Coupon.Type.MERCHANT, merchant_id=merchant_id))
            result.extend(merchant_coupons)
        return ok(request, CouponSerializer(result, many=True).data)


@extend_schema(tags=["coupon"], responses=EnvelopeResponse)
class ClaimCouponView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserCouponSerializer

    def post(self, request, coupon_id):
        user_coupon = claim_coupon(request.user, coupon_id)
        return ok(request, UserCouponSerializer(user_coupon).data, status_code=201)


@extend_schema(tags=["coupon"], responses=EnvelopeResponse)
class MyCouponsView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserCouponSerializer

    def get(self, request):
        from apps.coupons.services import list_user_coupons

        status = request.query_params.get("status")
        items = list_user_coupons(request.user, status=status)
        return ok(request, UserCouponSerializer(items, many=True).data)


@extend_schema(tags=["coupon"], responses=EnvelopeResponse)
class AvailableCouponsView(APIView):
    """下单页可用券：按商户+商品+金额匹配。"""

    permission_classes = [IsAuthenticated]
    serializer_class = UserCouponSerializer

    def get(self, request):
        merchant_id = int(request.query_params.get("merchant_id", 0))
        product_ids = request.query_params.getlist("product_id")
        amount = int(request.query_params.get("amount", 0))
        if not merchant_id or not product_ids:
            return ok(request, [])
        product_ids = [int(pid) for pid in product_ids]
        items = get_available_coupons(request.user, merchant_id=merchant_id, product_ids=product_ids, amount=amount)
        return ok(request, UserCouponSerializer(items, many=True).data)
