"""平台后台治理路由。"""

from django.urls import path

from .views import (
    AdminAuditBatchDecisionView,
    AdminAuditDecisionView,
    AdminAuditListView,
    AdminDecoPageDetailView,
    AdminDecoPageListView,
    AdminDecoPagePublishView,
    AdminMediaAssetDetailView,
    AdminMediaAssetListView,
    AdminMediaFolderDetailView,
    AdminMediaFolderListView,
    AdminOperationLogListView,
    AdminPlatformConfigView,
    AdminPopupAdListView,
    AdminPopupAdStatusView,
    AdminRulePublishView,
    AdminStoreNavView,
)

urlpatterns = [
    path("logs/", AdminOperationLogListView.as_view(), name="admin-operation-logs"),
    path("rules/", AdminRulePublishView.as_view(), name="admin-rules-publish"),
    path("audits/", AdminAuditListView.as_view(), name="admin-audits"),
    path("audits/batch-decision/", AdminAuditBatchDecisionView.as_view(), name="admin-audits-batch-decision"),
    path("audits/<int:pk>/decision/", AdminAuditDecisionView.as_view(), name="admin-audit-decision"),
    path("media-folders/", AdminMediaFolderListView.as_view(), name="admin-media-folders"),
    path("media-folders/<int:pk>/", AdminMediaFolderDetailView.as_view(), name="admin-media-folder-detail"),
    path("platform-config/", AdminPlatformConfigView.as_view(), name="admin-platform-config"),
    path("storefront/nav/", AdminStoreNavView.as_view(), name="admin-storefront-nav"),
    path("storefront/pages/", AdminDecoPageListView.as_view(), name="admin-deco-pages"),
    path("storefront/pages/<int:pk>/", AdminDecoPageDetailView.as_view(), name="admin-deco-page-detail"),
    path(
        "storefront/pages/<int:pk>/publish/",
        AdminDecoPagePublishView.as_view(),
        name="admin-deco-page-publish",
    ),
    path("media-assets/", AdminMediaAssetListView.as_view(), name="admin-media-assets"),
    path("media-assets/<int:pk>/", AdminMediaAssetDetailView.as_view(), name="admin-media-asset-detail"),
    path("popup-ads/", AdminPopupAdListView.as_view(), name="admin-popup-ads"),
    path("popup-ads/<int:pk>/<str:action>/", AdminPopupAdStatusView.as_view(), name="admin-popup-ad-status"),
]
