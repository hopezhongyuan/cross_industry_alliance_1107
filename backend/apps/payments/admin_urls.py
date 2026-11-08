"""平台支付配置路由。"""

from django.urls import path

from .views import PaymentConfigView

urlpatterns = [
    path("payment-configs/<str:channel>/", PaymentConfigView.as_view(), name="admin-payment-config"),
]
