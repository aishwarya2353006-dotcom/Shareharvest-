from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Donation
from .serializers import DonationSerializer
from accounts.models import User
from organizations.models import Organization, Membership
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from audit.services import log_audit
from donation_requests.services import donation_remaining_base


class IsDonationOwnerOrOrgAdminOrPlatformAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Platform administrators can perform any action
        if request.user.role == 'admin':
            return True
        # Check if the user is the donor of the donation
        if obj.donor == request.user:
            return True
        # Check if the user is an owner or admin of the organization
        return Membership.objects.filter(
            user=request.user, 
            organization=obj.organization, 
            role__in=['owner', 'admin'], 
            is_active=True
        ).exists()


class DonationViewSet(viewsets.ModelViewSet):
    queryset = Donation.objects.all()
    serializer_class = DonationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if self.request.query_params.get('browse', '').lower() in {'1', 'true', 'yes'}:
            if user.role != 'recipient':
                raise PermissionDenied('Only recipient users can browse available donations.')
            now = timezone.now()
            # Published offers are intentionally visible across donor organizations.
            # The request workflow remains authoritative for inventory and eligibility.
            offers = Donation.objects.filter(
                status='published', available_from__lte=now, available_until__gt=now
            ).select_related('organization')
            # Normally the allocation workflow changes exhausted offers to
            # ``reserved``. Calculate remaining stock too, so legacy or stale
            # published records cannot appear requestable.
            return [donation for donation in offers if donation_remaining_base(donation) > 0]
        if self.request.query_params.get('mine', '').lower() in {'1', 'true', 'yes'}:
            # The donor dashboard needs a complete, isolated set for this user,
            # including expired records. Never accept another donor's ID here.
            return Donation.objects.filter(donor=user)
        if user.role == 'admin':
            return Donation.objects.all()
        # Return donations from organizations the user is a member of
        qs = Donation.objects.filter(organization__in=Membership.objects.filter(user=user, is_active=True).values('organization_id'))
        # Exclude expired donations for non-admin users
        if user.role != 'admin':
            qs = qs.exclude(status='expired')
        return qs

    def get_serializer_class(self):
        if self.request.query_params.get('browse', '').lower() in {'1', 'true', 'yes'}:
            from .serializers import BrowseDonationSerializer
            return BrowseDonationSerializer
        return self.serializer_class

    def get_permissions(self):
        # For detail actions, we need to check object-level permissions
        if self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            return [IsDonationOwnerOrOrgAdminOrPlatformAdmin()]
        # For list and create, we only require authentication (we'll check organization membership in perform_create)
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        if self.request.user.role not in {'donor', 'admin'}:
            raise PermissionDenied('Only donor users can create donations.')
        # Set the donor to the requesting user
        # We also need to check that the user is a member of the organization
        organization_id = self.request.data.get('organization')
        if not organization_id:
            raise ValidationError({'organization': 'Organization is required.'})
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            raise ValidationError({'organization': 'Organization does not exist.'})
        # Check if the user is a member of the organization
        if not Membership.objects.filter(user=self.request.user, organization=organization, is_active=True).exists():
            raise PermissionDenied('You are not a member of this organization.')
        with transaction.atomic():
            donation = serializer.save(donor=self.request.user, organization=organization)
            log_audit(
                user=self.request.user, action='create', object_type='donation',
                object_id=donation.pk, object_repr=str(donation),
                request=self.request,
            )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Check object-level permissions (will use IsDonationOwnerOrOrgAdminOrPlatformAdmin)
        self.check_object_permissions(request, instance)
        # Prevent changing donor and organization
        if 'donor' in request.data or 'organization' in request.data:
            return Response({'detail': 'Donor and organization fields cannot be changed.'}, status=status.HTTP_400_BAD_REQUEST)
        # Validate status transitions
        new_status = request.data.get('status')
        if new_status is not None and new_status != instance.status:
            allowed_transitions = {
                'draft': {'published', 'cancelled'},
                'published': {'reserved', 'expired', 'cancelled'},
                'reserved': {'completed', 'expired', 'cancelled'},
                'expired': set(),
                'completed': set(),
                'cancelled': set(),
            }
            allowed = allowed_transitions.get(instance.status, set())
            if new_status not in allowed:
                return Response(
                    {'detail': f'Cannot transition donation from {instance.status} to {new_status}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # If status is being changed to published, check that the organization is verified
            if new_status == 'published':
                if instance.organization.status != 'verified':
                    return Response({'detail': 'Only verified organizations can publish donations.'}, status=status.HTTP_400_BAD_REQUEST)
        # Serialize donor quantity edits against approval transactions, which
        # lock this same inventory row before checking and recording allocations.
        with transaction.atomic():
            Donation.objects.select_for_update().get(pk=instance.pk)
            new_status = request.data.get('status')
            if new_status is not None and new_status != instance.status:
                log_audit(
                    user=request.user, action='update', object_type='donation',
                    object_id=instance.pk, object_repr=str(instance),
                    changes={'status': new_status}, request=request,
                )
            return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Check object-level permissions
        self.check_object_permissions(request, instance)
        # Prevent deletion if there are related workflow records
        from donation_requests.models import DonationRequest, DonationAllocation
        from pickups.models import Pickup
        if DonationRequest.objects.filter(donation=instance).exists():
            return Response(
                {'detail': 'Cannot delete donation with existing requests. Cancel or complete the workflow first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Pickup.objects.filter(donation=instance).exists():
            return Response(
                {'detail': 'Cannot delete donation with existing pickups. Pickups must be preserved for history.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)
