from rest_framework.routers import DefaultRouter
from .views import OrganizationComplianceViewSet, AllergenDeclarationViewSet, ComplianceDocumentViewSet

router = DefaultRouter()
router.register(r'organization-compliance', OrganizationComplianceViewSet, basename='organization-compliance')
router.register(r'allergen-declarations', AllergenDeclarationViewSet, basename='allergen-declaration')
router.register(r'compliance-documents', ComplianceDocumentViewSet, basename='compliance-document')

urlpatterns = router.urls
