from django.urls import path

from .views import AfterSaleCreateView, AfterSaleDetailView

urlpatterns = [
    path("", AfterSaleCreateView.as_view(), name="after-sale-create"),
    path("<int:pk>/", AfterSaleDetailView.as_view(), name="after-sale-detail"),
]
