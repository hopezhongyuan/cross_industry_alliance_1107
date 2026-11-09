"""URL 总表：/api/v1 为业务接口，/api/schema 为契约，/admin 为平台运营后台。"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/", include("apps.common.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.merchants.urls")),
    path("api/v1/", include("apps.orders.urls")),
    path("api/v1/", include("apps.accounts.consumer_urls")),
    path("api/v1/", include("apps.governance.public_urls")),
    path("api/v1/", include("apps.points.consumer_urls")),
    path("api/v1/", include("apps.payments.consumer_urls")),
    path("api/v1/after-sales/", include("apps.aftersales.urls")),
    path("api/v1/merchant/", include("apps.orders.merchant_urls")),
    path("api/v1/merchant/", include("apps.catalog.merchant_urls")),
    path("api/v1/merchant/", include("apps.aftersales.merchant_urls")),
    path("api/v1/merchant/", include("apps.ledger.merchant_urls")),
    path("api/v1/merchant/", include("apps.merchants.merchant_urls")),
    path("api/v1/admin/", include("apps.accounts.admin_urls")),
    path("api/v1/admin/", include("apps.merchants.admin_urls")),
    path("api/v1/admin/", include("apps.catalog.admin_urls")),
    path("api/v1/admin/", include("apps.aftersales.admin_urls")),
    path("api/v1/admin/", include("apps.orders.admin_urls")),
    path("api/v1/admin/", include("apps.ledger.admin_urls")),
    path("api/v1/admin/", include("apps.governance.urls")),
    path("api/v1/admin/", include("apps.payments.admin_urls")),
    path("api/v1/admin/", include("apps.points.admin_urls")),
    path("api/v1/callback/wechat/", include("apps.payments.urls")),
    path("api/v1/accounts/", include("apps.accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
