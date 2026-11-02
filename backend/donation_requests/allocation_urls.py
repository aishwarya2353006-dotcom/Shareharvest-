from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DonationAllocationViewSet


router = DefaultRouter()
router.register(r'', DonationAllocationViewSet, basename='donation-allocation')

urlpatterns = [path('', include(router.urls))]
