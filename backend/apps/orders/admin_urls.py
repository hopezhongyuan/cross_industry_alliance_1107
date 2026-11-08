"""平台后台订单路由。"""

from django.urls import path

from .admin_views import AdminOrderDetailView, AdminOrderListView

urlpatterns = [
    path("orders/", AdminOrderListView.as_view(), name="admin-orders"),
    path("orders/<int:pk>/", AdminOrderDetailView.as_view(), name="admin-order-detail"),
]
