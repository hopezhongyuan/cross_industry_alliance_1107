"""平台后台治理路由。"""

from django.urls import path

from .views import AdminOperationLogListView, AdminRulePublishView

urlpatterns = [
    path("logs/", AdminOperationLogListView.as_view(), name="admin-operation-logs"),
    path("rules/", AdminRulePublishView.as_view(), name="admin-rules-publish"),
]
