"""商户中心商品与分类路由。"""

from django.urls import path

from .merchant_views import (
    MerchantProductCategoryDetailView,
    MerchantProductCategoryListView,
    MerchantProductDetailView,
    MerchantProductListView,
    MerchantProductStatusView,
    MerchantTemplateAdoptView,
    MerchantTemplateListView,
)

urlpatterns = [
    path("products/", MerchantProductListView.as_view(), name="merchant-products"),
    path("products/<int:pk>/", MerchantProductDetailView.as_view(), name="merchant-product-detail"),
    path("products/<int:pk>/status/", MerchantProductStatusView.as_view(), name="merchant-product-status"),
    path("product-categories/", MerchantProductCategoryListView.as_view(), name="merchant-product-categories"),
    path(
        "product-categories/<int:pk>/",
        MerchantProductCategoryDetailView.as_view(),
        name="merchant-product-category-detail",
    ),
    path("product-templates/", MerchantTemplateListView.as_view(), name="merchant-product-templates"),
    path(
        "product-templates/<int:pk>/adopt/",
        MerchantTemplateAdoptView.as_view(),
        name="merchant-product-template-adopt",
    ),
]
