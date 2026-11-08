"""平台后台售后/仲裁路由。"""

from django.urls import path

from .views import AdminArbitrationRuleView

urlpatterns = [
    path("arbitrations/<int:pk>/rule/", AdminArbitrationRuleView.as_view(), name="admin-arbitration-rule"),
]
