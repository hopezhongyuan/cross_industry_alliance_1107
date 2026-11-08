"""平台后台用户路由。"""

from django.urls import path

from .views import AdminUserListView

urlpatterns = [
    path("users/", AdminUserListView.as_view(), name="admin-users"),
]
