from django.urls import path

from .views import MerchantAcceptView, MerchantOrderListView, MerchantRejectView, MerchantShipView, MerchantVerifyView

urlpatterns = [
    path("orders/", MerchantOrderListView.as_view(), name="merchant-orders"),
    path("orders/<int:pk>/accept/", MerchantAcceptView.as_view(), name="merchant-order-accept"),
    path("orders/<int:pk>/reject/", MerchantRejectView.as_view(), name="merchant-order-reject"),
    path("orders/<int:pk>/ship/", MerchantShipView.as_view(), name="merchant-order-ship"),
    path("verify/", MerchantVerifyView.as_view(), name="merchant-verify"),
]
