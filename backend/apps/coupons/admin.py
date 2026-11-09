from django.contrib import admin

from apps.common.admin import BaseAdmin

from .models import Coupon, UserCoupon


@admin.register(Coupon)
class CouponAdmin(BaseAdmin):
    list_display = ("coupon_no", "name", "type", "merchant", "face_value", "min_amount", "status")
    list_filter = ("type", "status")
    search_fields = ("coupon_no", "name")


@admin.register(UserCoupon)
class UserCouponAdmin(BaseAdmin):
    list_display = ("user_coupon_no", "user", "coupon", "status", "expire_at")
    list_filter = ("status",)
    search_fields = ("user_coupon_no",)
