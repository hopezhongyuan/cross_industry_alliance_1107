from django.urls import path

from .views import MerchantAcceptView, MerchantRejectView, MerchantShipView, MerchantVerifyView

urlpatterns = [
    path("orders/<int:pk>/accept/", MerchantAcceptView.as_view(), name="merchant-order-accept"),
    path("orders/<int:pk>/reject/", MerchantRejectView.as_view(), name="merchant-order-reject"),
    path("orders/<int:pk>/ship/", MerchantShipView.as_view(), name="merchant-order-ship"),
    path("verify/", MerchantVerifyView.as_view(), name="merchant-verify"),
]
