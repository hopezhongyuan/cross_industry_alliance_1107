"""平台后台商品类目、商品与模板路由。"""

from django.urls import path

from .admin_views import (
    AdminCategoryDetailView,
    AdminCategoryListView,
    AdminProductDetailView,
    AdminProductListView,
    AdminProductStatusView,
    AdminTemplateDetailView,
    AdminTemplateListView,
    AdminTemplateSyncView,
)

urlpatterns = [
    path("categories/", AdminCategoryListView.as_view(), name="admin-categories"),
    path("categories/<int:pk>/", AdminCategoryDetailView.as_view(), name="admin-category-detail"),
    path("products/", AdminProductListView.as_view(), name="admin-products"),
    path("products/<int:pk>/", AdminProductDetailView.as_view(), name="admin-product-detail"),
    path("products/<int:pk>/status/", AdminProductStatusView.as_view(), name="admin-product-status"),
    path("product-templates/", AdminTemplateListView.as_view(), name="admin-product-templates"),
    path("product-templates/<int:pk>/", AdminTemplateDetailView.as_view(), name="admin-product-template-detail"),
    path(
        "product-templates/<int:pk>/sync/",
        AdminTemplateSyncView.as_view(),
        name="admin-product-template-sync",
    ),
]
