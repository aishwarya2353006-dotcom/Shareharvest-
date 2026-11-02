from rest_framework.routers import DefaultRouter
from .views import ImpactReportViewSet

router = DefaultRouter()
router.register(r'', ImpactReportViewSet, basename='impact')

urlpatterns = router.urls
