"""平台商户管理路由。"""

from django.urls import path

from .views import AdminMerchantDetailView, AdminMerchantListView, AdminMerchantStatusView

urlpatterns = [
    path("merchants/", AdminMerchantListView.as_view(), name="admin-merchants"),
    path("merchants/<int:pk>/", AdminMerchantDetailView.as_view(), name="admin-merchant-detail"),
    path("merchants/<int:pk>/status/", AdminMerchantStatusView.as_view(), name="admin-merchant-status"),
]
