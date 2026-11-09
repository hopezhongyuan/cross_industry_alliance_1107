"""平台后台积分路由（挂载在 /api/v1/admin/ 下）。"""

from django.urls import path

from .admin_views import (
    AdminPointsAdjustView,
    AdminPointsConfigView,
    AdminPointsUserListView,
    AdminPointsUserTransactionView,
)

urlpatterns = [
    path("points/config/", AdminPointsConfigView.as_view(), name="admin-points-config"),
    path("points/users/", AdminPointsUserListView.as_view(), name="admin-points-users"),
    path(
        "points/users/<int:user_id>/transactions/",
        AdminPointsUserTransactionView.as_view(),
        name="admin-points-user-txns",
    ),
    path("points/adjust/", AdminPointsAdjustView.as_view(), name="admin-points-adjust"),
]
