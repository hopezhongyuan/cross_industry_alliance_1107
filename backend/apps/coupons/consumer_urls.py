from django.urls import path

from .consumer_views import AvailableCouponsView, ClaimCouponView, CouponCenterView, MyCouponsView

urlpatterns = [
    path("coupons/", CouponCenterView.as_view(), name="coupon-center"),
    path("coupons/<int:coupon_id>/claim/", ClaimCouponView.as_view(), name="coupon-claim"),
    path("user/coupons/", MyCouponsView.as_view(), name="my-coupons"),
    path("user/coupons/available/", AvailableCouponsView.as_view(), name="available-coupons"),
]
