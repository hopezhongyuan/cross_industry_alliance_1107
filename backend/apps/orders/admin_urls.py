"""平台后台订单路由。"""

from django.urls import path

from .admin_views import AdminOrderListView

urlpatterns = [
    path("orders/", AdminOrderListView.as_view(), name="admin-orders"),
]
