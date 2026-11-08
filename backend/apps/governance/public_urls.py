"""公开治理接口：平台基础信息，供消费者端读取。"""

from django.urls import path

from .views import PublicDecoPageView, PublicPlatformConfigView, PublicStoreNavView

urlpatterns = [
    path("platform/config/", PublicPlatformConfigView.as_view(), name="public-platform-config"),
    path("storefront/nav/", PublicStoreNavView.as_view(), name="public-storefront-nav"),
    path("storefront/pages/<str:slug>/", PublicDecoPageView.as_view(), name="public-deco-page"),
]
