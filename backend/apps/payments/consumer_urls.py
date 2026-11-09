from django.urls import path

from .views import GroupPayView

urlpatterns = [
    path("payment-groups/<str:group_no>/pay/", GroupPayView.as_view(), name="group-pay"),
]
