"""平台后台售后/仲裁路由。"""

from django.urls import path

from .views import AdminArbitrationDetailView, AdminArbitrationListView, AdminArbitrationRuleView

urlpatterns = [
    path("arbitrations/", AdminArbitrationListView.as_view(), name="admin-arbitrations"),
    path("arbitrations/<int:pk>/", AdminArbitrationDetailView.as_view(), name="admin-arbitration-detail"),
    path("arbitrations/<int:pk>/rule/", AdminArbitrationRuleView.as_view(), name="admin-arbitration-rule"),
]
