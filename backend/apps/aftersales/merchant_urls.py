from django.urls import path

from .views import AfterSaleDecisionView, MerchantAfterSaleListView

urlpatterns = [
    path("after-sales/", MerchantAfterSaleListView.as_view(), name="merchant-after-sales"),
    path("after-sales/<int:pk>/decision/", AfterSaleDecisionView.as_view(), name="after-sale-decision"),
]
