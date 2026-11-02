from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .models import OrganizationCompliance, AllergenDeclaration, ComplianceDocument
from .serializers import (
    OrganizationComplianceSerializer, OrganizationComplianceCreateSerializer,
    OrganizationComplianceVerifySerializer, AllergenDeclarationSerializer,
    AllergenDeclarationCreateSerializer, AllergenDeclarationReviewSerializer,
    ComplianceDocumentSerializer, ComplianceDocumentCreateSerializer,
)
from organizations.models import Organization, Membership
from donations.models import Donation
from audit.services import log_audit


class IsOrgOwnerOrAdminOrPlatformAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        organization = getattr(obj, 'organization', None)
        if organization is None:
            return False
        return Membership.objects.filter(
            user=request.user, organization=organization,
            role__in=['owner', 'admin'], is_active=True
        ).exists()


class IsPlatformAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'admin'


class OrganizationComplianceViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationComplianceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            queryset = OrganizationCompliance.objects.select_related('organization').all()
        else:
            queryset = OrganizationCompliance.objects.select_related('organization').filter(
                organization__in=Membership.objects.filter(
                    user=user, is_active=True
                ).values('organization_id')
            )
        organization_id = self.request.query_params.get('organization')
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return OrganizationComplianceCreateSerializer
        return OrganizationComplianceSerializer

    def get_permissions(self):
        if self.action in ['verify', 'reject']:
            return [IsPlatformAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        user = self.request.user
        organization_id = self.request.data.get('organization')
        if not organization_id:
            raise ValidationError({'organization': 'Organization is required.'})
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise ValidationError({'organization': 'Organization does not exist.'})
        if not Membership.objects.filter(
            user=user, organization=organization, is_active=True,
            role__in=['owner', 'admin']
        ).exists():
            if user.role != 'admin':
                raise PermissionDenied('You are not an owner or admin of this organization.')
        if OrganizationCompliance.objects.filter(organization=organization).exists():
            raise ValidationError({'organization': 'A compliance record already exists for this organization.'})
        with transaction.atomic():
            compliance = serializer.save(organization=organization)
            compliance.compliance_status = 'submitted'
            compliance.submitted_at = timezone.now()
            compliance.save(update_fields=['compliance_status', 'submitted_at'])
            log_audit(
                user=user, action='create', object_type='organization_compliance',
                object_id=compliance.pk, object_repr=str(compliance),
                request=self.request,
            )

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        compliance = self.get_object()
        serializer = OrganizationComplianceVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        if action != 'verify':
            return Response({'detail': 'Use the reject action for rejection.'}, status=status.HTTP_400_BAD_REQUEST)
        if compliance.compliance_status == 'verified':
            return Response({'detail': 'Compliance record is already verified.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            compliance.compliance_status = 'verified'
            compliance.verified_at = timezone.now()
            compliance.verified_by = request.user
            compliance.rejection_reason = ''
            compliance.save(update_fields=[
                'compliance_status', 'verified_at', 'verified_by', 'rejection_reason', 'updated_at'
            ])
            log_audit(
                user=request.user, action='verify', object_type='organization_compliance',
                object_id=compliance.pk, object_repr=str(compliance),
                changes={'status': 'verified'}, request=request,
            )
        return Response(OrganizationComplianceSerializer(compliance).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        compliance = self.get_object()
        serializer = OrganizationComplianceVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        if action != 'reject':
            return Response({'detail': 'Use the verify action for verification.'}, status=status.HTTP_400_BAD_REQUEST)
        rejection_reason = serializer.validated_data.get('rejection_reason', '')
        if not rejection_reason:
            return Response(
                {'rejection_reason': 'A rejection reason is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            compliance.compliance_status = 'rejected'
            compliance.rejection_reason = rejection_reason
            notes = serializer.validated_data.get('notes', '')
            if notes:
                compliance.notes = notes
            compliance.save(update_fields=[
                'compliance_status', 'rejection_reason', 'notes', 'updated_at'
            ])
            log_audit(
                user=request.user, action='reject', object_type='organization_compliance',
                object_id=compliance.pk, object_repr=str(compliance),
                changes={'status': 'rejected', 'reason': rejection_reason}, request=request,
            )
        return Response(OrganizationComplianceSerializer(compliance).data)

    @action(detail=False, methods=['get'], url_path='my-compliance')
    def my_compliance(self, request):
        user = request.user
        if user.role == 'admin':
            return Response({'detail': 'Admins should use the list endpoint.'}, status=status.HTTP_400_BAD_REQUEST)
        orgs = Organization.objects.filter(
            memberships__user=user, memberships__is_active=True
        ).distinct()
        records = OrganizationCompliance.objects.filter(organization__in=orgs)
        page = self.paginate_queryset(records)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)


class AllergenDeclarationViewSet(viewsets.ModelViewSet):
    serializer_class = AllergenDeclarationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return AllergenDeclaration.objects.select_related(
                'donation', 'declared_by', 'reviewed_by'
            ).all()
        return AllergenDeclaration.objects.select_related(
            'donation', 'declared_by', 'reviewed_by'
        ).filter(
            donation__organization__in=Membership.objects.filter(
                user=user, is_active=True
            ).values('organization_id')
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return AllergenDeclarationCreateSerializer
        return AllergenDeclarationSerializer

    def get_permissions(self):
        if self.action in ['verify', 'reject']:
            return [IsPlatformAdmin()]
        if self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated(), IsOrgOwnerOrAdminOrPlatformAdmin()]
        return [permissions.IsAuthenticated()]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        self.check_object_permissions(request, instance)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        self.check_object_permissions(request, instance)
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        donation_id = self.request.data.get('donation')
        if not donation_id:
            raise ValidationError({'donation': 'Donation is required.'})
        try:
            donation = Donation.objects.get(id=donation_id)
        except Donation.DoesNotExist:
            raise ValidationError({'donation': 'Donation does not exist.'})
        if not Membership.objects.filter(
            user=user, organization=donation.organization, is_active=True,
            role__in=['owner', 'admin']
        ).exists():
            if user.role != 'admin':
                raise PermissionDenied('You are not an owner or admin of this donation\'s organization.')
        if AllergenDeclaration.objects.filter(donation=donation).exists():
            raise ValidationError({'donation': 'An allergen declaration already exists for this donation.'})
        with transaction.atomic():
            declaration = serializer.save(donation=donation, declared_by=user)
            log_audit(
                user=user, action='create', object_type='allergen_declaration',
                object_id=declaration.pk, object_repr=str(declaration),
                request=self.request,
            )

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        declaration = self.get_object()
        serializer = AllergenDeclarationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        if action != 'verify':
            return Response({'detail': 'Use the reject action for rejection.'}, status=status.HTTP_400_BAD_REQUEST)
        if declaration.declaration_status == 'verified':
            return Response({'detail': 'Allergen declaration is already verified.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            declaration.declaration_status = 'verified'
            declaration.reviewed_by = request.user
            declaration.reviewed_at = timezone.now()
            declaration.review_notes = serializer.validated_data.get('review_notes', '')
            declaration.save(update_fields=[
                'declaration_status', 'reviewed_by', 'reviewed_at',
                'review_notes', 'updated_at',
            ])
            log_audit(
                user=request.user, action='verify', object_type='allergen_declaration',
                object_id=declaration.pk, object_repr=str(declaration),
                changes={'status': 'verified'}, request=request,
            )
        return Response(AllergenDeclarationSerializer(declaration).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        declaration = self.get_object()
        serializer = AllergenDeclarationReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        if action != 'reject':
            return Response({'detail': 'Use the verify action for verification.'}, status=status.HTTP_400_BAD_REQUEST)
        review_notes = serializer.validated_data.get('review_notes', '')
        if not review_notes:
            return Response(
                {'review_notes': 'A review note is required for rejection.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            declaration.declaration_status = 'rejected'
            declaration.reviewed_by = request.user
            declaration.reviewed_at = timezone.now()
            declaration.review_notes = review_notes
            declaration.save(update_fields=[
                'declaration_status', 'reviewed_by', 'reviewed_at',
                'review_notes', 'updated_at',
            ])
            log_audit(
                user=request.user, action='reject', object_type='allergen_declaration',
                object_id=declaration.pk, object_repr=str(declaration),
                changes={'status': 'rejected', 'notes': review_notes}, request=request,
            )
        return Response(AllergenDeclarationSerializer(declaration).data)

    @action(detail=False, methods=['get'], url_path='my-declarations')
    def my_declarations(self, request):
        user = request.user
        if user.role == 'admin':
            return Response({'detail': 'Admins should use the list endpoint.'}, status=status.HTTP_400_BAD_REQUEST)
        orgs = Organization.objects.filter(
            memberships__user=user, memberships__is_active=True
        ).distinct()
        declarations = AllergenDeclaration.objects.filter(donation__organization__in=orgs)
        page = self.paginate_queryset(declarations)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(declarations, many=True)
        return Response(serializer.data)


class ComplianceDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = ComplianceDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return ComplianceDocument.objects.select_related(
                'organization', 'uploaded_by', 'verified_by'
            ).all()
        return ComplianceDocument.objects.select_related(
            'organization', 'uploaded_by', 'verified_by'
        ).filter(
            organization__in=Membership.objects.filter(
                user=user, is_active=True
            ).values('organization_id')
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return ComplianceDocumentCreateSerializer
        return ComplianceDocumentSerializer

    def perform_create(self, serializer):
        user = self.request.user
        organization_id = self.request.data.get('organization')
        if not organization_id:
            raise ValidationError({'organization': 'Organization is required.'})
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise ValidationError({'organization': 'Organization does not exist.'})
        if not Membership.objects.filter(
            user=user, organization=organization, is_active=True,
            role__in=['owner', 'admin']
        ).exists():
            if user.role != 'admin':
                raise PermissionDenied('You are not an owner or admin of this organization.')
        with transaction.atomic():
            document = serializer.save(organization=organization, uploaded_by=user)
            log_audit(
                user=user, action='create', object_type='compliance_document',
                object_id=document.pk, object_repr=str(document),
                request=self.request,
            )
