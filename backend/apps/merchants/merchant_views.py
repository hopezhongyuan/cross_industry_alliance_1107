"""商户端自身资料与经营看板。"""

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated

from apps.common.api import EnvelopeAPIView, EnvelopeResponse, ok

from .serializers import MerchantSelfProfileSerializer
from .services import get_active_staff_merchant


@extend_schema(tags=["merchant"], responses=EnvelopeResponse)
class MerchantProfileView(EnvelopeAPIView):
    """当前登录商户的自身资料（名称、Logo、地址等）。"""

    permission_classes = [IsAuthenticated]
    serializer_class = EnvelopeResponse

    def get(self, request):
        merchant = get_active_staff_merchant(request.user)
        return ok(request, MerchantSelfProfileSerializer(merchant).data)


@extend_schema(tags=["merchant"], responses=EnvelopeResponse)
class MerchantDashboardView(EnvelopeAPIView):
    """商户首页数据看板；所有"今日"口径为 Asia/Shanghai 自然日。"""

    permission_classes = [IsAuthenticated]
    serializer_class = EnvelopeResponse

    def get(self, request):
        from apps.aftersales.models import AfterSale
        from apps.catalog.models import Product
        from apps.fulfillment.models import VerifyCode
        from apps.ledger.models import MerchantAccount
        from apps.orders.models import Order

        merchant = get_active_staff_merchant(request.user)
        today = timezone.localdate()

        today_orders = Order.objects.filter(merchant=merchant, created_at__date=today).count()
        today_sales_amount = (
            Order.objects.filter(merchant=merchant, paid_at__date=today).aggregate(
                total=Coalesce(Sum("paid_amount"), 0)
            )["total"]
            or 0
        )
        pending_orders = Order.objects.filter(
            merchant=merchant, status__in=(Order.Status.PENDING_ACCEPT, Order.Status.PENDING_FULFILL)
        ).count()
        pending_after_sales = AfterSale.objects.filter(
            merchant=merchant, merchant_decision=AfterSale.MerchantDecision.PENDING
        ).count()
        pending_products = Product.objects.filter(merchant=merchant, status=Product.Status.PENDING_AUDIT).count()
        today_refund_count = AfterSale.objects.filter(merchant=merchant, created_at__date=today).count()
        today_verified_count = VerifyCode.objects.filter(
            merchant=merchant, status=VerifyCode.Status.USED, used_at__date=today
        ).count()

        account = MerchantAccount.objects.filter(merchant_id=merchant.id).first()
        available_balance = account.available_balance if account else 0

        return ok(
            request,
            {
                "today_orders": today_orders,
                "today_sales_amount": today_sales_amount,
                "pending_orders": pending_orders,
                "pending_after_sales": pending_after_sales,
                "pending_products": pending_products,
                "available_balance": available_balance,
                "today_refund_count": today_refund_count,
                "today_verified_count": today_verified_count,
            },
        )
