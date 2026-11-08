"""平台后台治理路由。"""

from django.urls import path

from .views import (
    AdminAuditDecisionView,
    AdminAuditListView,
    AdminMediaAssetDetailView,
    AdminMediaAssetListView,
    AdminMediaFolderDetailView,
    AdminMediaFolderListView,
    AdminOperationLogListView,
    AdminRulePublishView,
)

urlpatterns = [
    path("logs/", AdminOperationLogListView.as_view(), name="admin-operation-logs"),
    path("rules/", AdminRulePublishView.as_view(), name="admin-rules-publish"),
    path("audits/", AdminAuditListView.as_view(), name="admin-audits"),
    path("audits/<int:pk>/decision/", AdminAuditDecisionView.as_view(), name="admin-audit-decision"),
    path("media-folders/", AdminMediaFolderListView.as_view(), name="admin-media-folders"),
    path("media-folders/<int:pk>/", AdminMediaFolderDetailView.as_view(), name="admin-media-folder-detail"),
    path("media-assets/", AdminMediaAssetListView.as_view(), name="admin-media-assets"),
    path("media-assets/<int:pk>/", AdminMediaAssetDetailView.as_view(), name="admin-media-asset-detail"),
]
