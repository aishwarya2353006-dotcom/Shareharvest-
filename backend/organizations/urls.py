from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrganizationViewSet, MembershipViewSet

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'memberships', MembershipViewSet, basename='membership')

urlpatterns = [
    path('', include(router.urls)),
]