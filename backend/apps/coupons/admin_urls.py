from django.urls import path

from .admin_views import AdminCouponListView, AdminCouponStatusView

urlpatterns = [
    path("coupons/", AdminCouponListView.as_view(), name="admin-coupon-list"),
    path("coupons/<int:coupon_id>/<str:action>/", AdminCouponStatusView.as_view(), name="admin-coupon-status"),
]
