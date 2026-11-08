from django.urls import path

from .views import AfterSaleDecisionView

urlpatterns = [
    path("after-sales/<int:pk>/decision/", AfterSaleDecisionView.as_view(), name="after-sale-decision"),
]
