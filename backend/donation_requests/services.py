from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from organizations.models import Membership


# Comparisons use a base unit within each dimension. Count units stay distinct
# because the contents of a box or tray are not defined by the current schema.
UNIT_DIMENSIONS = {
    'kg': ('mass', Decimal('1000')),
    'g': ('mass', Decimal('1')),
    'l': ('volume', Decimal('1000')),
    'ml': ('volume', Decimal('1')),
    'units': ('count:units', Decimal('1')),
    'boxes': ('count:boxes', Decimal('1')),
    'trays': ('count:trays', Decimal('1')),
}


def units_compatible(unit_a, unit_b):
    return (
        unit_a in UNIT_DIMENSIONS
        and unit_b in UNIT_DIMENSIONS
        and UNIT_DIMENSIONS[unit_a][0] == UNIT_DIMENSIONS[unit_b][0]
    )


def quantity_in_base(quantity, unit):
    """Return a Decimal in grams, milliliters, or the same named count unit."""
    try:
        dimension, factor = UNIT_DIMENSIONS[unit]
    except (KeyError, TypeError):
        raise ValidationError({'unit': 'Unsupported quantity unit.'})
    return Decimal(str(quantity)) * factor, dimension


def convert_quantity(quantity, from_unit, to_unit):
    value, source_dimension = quantity_in_base(quantity, from_unit)
    _, target_dimension = quantity_in_base(1, to_unit)
    if source_dimension != target_dimension:
        raise ValidationError({'unit': 'The quantity units are not compatible.'})
    return value / UNIT_DIMENSIONS[to_unit][1]


def allocations_for_donation(donation, *, exclude_request_id=None):
    from .models import DonationAllocation

    allocations = DonationAllocation.objects.filter(request__donation=donation)
    if exclude_request_id is not None:
        allocations = allocations.exclude(request_id=exclude_request_id)
    return allocations


def allocated_quantity_base(donation, *, exclude_request_id=None):
    total = Decimal('0')
    for quantity, unit in allocations_for_donation(
        donation, exclude_request_id=exclude_request_id
    ).values_list('approved_quantity', 'approved_unit'):
        amount, dimension = quantity_in_base(quantity, unit)
        donation_dimension, _ = UNIT_DIMENSIONS[donation.unit]
        if dimension != donation_dimension:
            # Legacy or manually inserted invalid allocations must not be
            # counted as compatible stock. New writes are rejected by validation.
            continue
        total += amount
    return total


def request_allocated_quantity_base(request):
    total = Decimal('0')
    for quantity, unit in request.allocations.values_list(
        'approved_quantity', 'approved_unit'
    ):
        amount, dimension = quantity_in_base(quantity, unit)
        requested_dimension, _ = UNIT_DIMENSIONS[request.requested_unit]
        if dimension == requested_dimension:
            total += amount
    return total


def donation_remaining_base(donation):
    quantity, _ = quantity_in_base(donation.quantity, donation.unit)
    return quantity - allocated_quantity_base(donation)


def request_remaining_base(request):
    quantity, _ = quantity_in_base(request.requested_quantity, request.requested_unit)
    return quantity - request_allocated_quantity_base(request)


def validate_request_values(*, user, organization, donation, quantity, unit):
    if user.role != 'recipient':
        raise ValidationError({'detail': 'Only recipient users can request donations.'})
    if organization.status != 'verified' or organization.org_type not in {
        'ngo', 'trust', 'community'
    }:
        raise ValidationError({
            'organization': 'Requests require a verified recipient organization.'
        })
    if not Membership.objects.filter(
        user=user, organization=organization, is_active=True
    ).exists():
        raise ValidationError({'organization': 'You must be an active organization member.'})
    if donation.organization_id == organization.pk:
        raise ValidationError({'donation': 'An organization cannot request its own donation.'})
    now = timezone.now()
    if donation.status != 'published':
        raise ValidationError({'donation': 'Only published donations can be requested.'})
    if donation.available_from > now:
        raise ValidationError({'donation': 'This donation is not available yet.'})
    if donation.available_until <= now:
        raise ValidationError({'donation': 'This donation has expired.'})
    if not units_compatible(donation.unit, unit):
        raise ValidationError({
            'requested_unit': 'The requested unit must be compatible with the donation unit.'
        })
    requested_base, _ = quantity_in_base(quantity, unit)
    remaining_base = donation_remaining_base(donation)
    if requested_base <= 0:
        raise ValidationError({'requested_quantity': 'Quantity must be greater than zero.'})
    if requested_base > remaining_base:
        raise ValidationError({
            'requested_quantity': 'Requested quantity exceeds the donation quantity still available.'
        })
