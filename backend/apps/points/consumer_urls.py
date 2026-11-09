"""消费者端积分路由（挂载在 /api/v1/ 下）。"""

from django.urls import path

from .consumer_views import (
    PointAccountView,
    PointRulesView,
    PointShareView,
    PointSigninView,
    PointTransactionListView,
)

urlpatterns = [
    path("points/account/", PointAccountView.as_view(), name="point-account"),
    path("points/transactions/", PointTransactionListView.as_view(), name="point-transactions"),
    path("points/signin/", PointSigninView.as_view(), name="point-signin"),
    path("points/share/", PointShareView.as_view(), name="point-share"),
    path("points/rules/", PointRulesView.as_view(), name="point-rules"),
]
