from decimal import Decimal
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.db.models import Sum
from organizations.models import Membership, Organization
from donations.models import Donation
from donation_requests.models import DonationAllocation
from pickups.models import Pickup


class ImpactReportViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def _get_user_orgs(self, user):
        if user.role == 'admin':
            return Organization.objects.all()
        return Organization.objects.filter(
            memberships__user=user, memberships__is_active=True
        ).distinct()

    @action(detail=False, methods=['get'])
    def summary(self, request):
        orgs = self._get_user_orgs(request.user)
        completed_pickups = Pickup.objects.filter(
            status='completed',
            donation__organization__in=orgs
        ).count() if orgs else 0
        total_allocated_kg = Decimal('0')
        allocations = DonationAllocation.objects.filter(
            request__donation__organization__in=orgs
        ) if orgs else DonationAllocation.objects.none()
        from donation_requests.services import quantity_in_base
        for qty, unit in allocations.values_list('approved_quantity', 'approved_unit'):
            try:
                amount, dimension = quantity_in_base(qty, unit)
                # quantity_in_base returns grams for mass units; convert to kg.
                # Volume and count units cannot be converted to kg without
                # density information, so they are excluded from the kg total
                # rather than fabricating a mixed-unit value.
                if dimension == 'mass':
                    total_allocated_kg += amount / Decimal('1000')
            except Exception:
                pass
        donations_published = Donation.objects.filter(
            organization__in=orgs, status='published'
        ).count() if orgs else 0
        return Response({
            'completed_pickups': completed_pickups,
            'total_allocated_kg': float(total_allocated_kg),
            'donations_published': donations_published,
            'organizations': orgs.count(),
        })

