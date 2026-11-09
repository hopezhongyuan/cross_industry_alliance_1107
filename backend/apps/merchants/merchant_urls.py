"""商户端自身资料与数据看板路由。"""

from django.urls import path

from .merchant_views import MerchantDashboardView, MerchantProfileView

urlpatterns = [
    path("profile/", MerchantProfileView.as_view(), name="merchant-profile"),
    path("dashboard/", MerchantDashboardView.as_view(), name="merchant-dashboard"),
]
