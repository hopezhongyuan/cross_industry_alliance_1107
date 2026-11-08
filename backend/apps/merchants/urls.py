from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MerchantViewSet, StoreDetailView, StoreNearbyView

router = DefaultRouter()
router.register("merchants", MerchantViewSet, basename="merchant")

urlpatterns = [
    path("stores/nearby/", StoreNearbyView.as_view(), name="store-nearby"),
    path("stores/<int:pk>/", StoreDetailView.as_view(), name="store-detail"),
] + router.urls
