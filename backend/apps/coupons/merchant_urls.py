from django.urls import path

from .merchant_views import MerchantCouponListView, MerchantCouponStatusView

urlpatterns = [
    path("coupons/", MerchantCouponListView.as_view(), name="merchant-coupon-list"),
    path("coupons/<int:coupon_id>/<str:action>/", MerchantCouponStatusView.as_view(), name="merchant-coupon-status"),
]
