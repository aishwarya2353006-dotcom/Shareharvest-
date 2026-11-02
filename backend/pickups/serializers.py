from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from donations.models import Donation
from donation_requests.models import DonationAllocation
from donation_requests.services import quantity_in_base, units_compatible
from .models import Pickup


class PickupSerializer(serializers.ModelSerializer):
    allocation = serializers.PrimaryKeyRelatedField(
        queryset=DonationAllocation.objects.select_related(
            'request', 'request__donation', 'request__organization'
        )
    )
    donation = serializers.IntegerField(source='donation_id', read_only=True)
    request = serializers.IntegerField(source='request_id', read_only=True)
    status = serializers.CharField(read_only=True)
    volunteer = serializers.PrimaryKeyRelatedField(read_only=True)
    volunteer_username = serializers.CharField(
        source='volunteer.username', read_only=True, default=None
    )
    donation_title = serializers.CharField(source='donation.title', read_only=True)
    donation_unit = serializers.CharField(source='donation.unit', read_only=True)
    allocation_quantity = serializers.DecimalField(
        source='allocation.approved_quantity', max_digits=10, decimal_places=2, read_only=True
    )
    allocation_unit = serializers.CharField(
        source='allocation.approved_unit', read_only=True
    )
    donor_organization_name = serializers.CharField(
        source='donation.organization.name', read_only=True
    )
    recipient_organization_name = serializers.CharField(
        source='request.organization.name', read_only=True
    )

    class Meta:
        model = Pickup
        fields = [
            'id', 'donation', 'request', 'allocation', 'donation_title',
            'donation_unit', 'allocation_quantity', 'allocation_unit',
            'donor_organization_name', 'recipient_organization_name',
            'pickup_type', 'scheduled_at', 'started_at', 'completed_at',
            'cancelled_at', 'no_show_at', 'failed_at', 'status', 'volunteer',
            'volunteer_username', 'pickup_address', 'contact_person',
            'contact_phone', 'notes', 'failure_reason',
            'actual_quantity', 'actual_unit',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'donation', 'request', 'status', 'volunteer',
            'volunteer_username', 'donation_title', 'donation_unit',
            'allocation_quantity', 'allocation_unit', 'donor_organization_name',
            'recipient_organization_name', 'started_at', 'completed_at',
            'cancelled_at', 'no_show_at', 'failed_at', 'failure_reason',
            'actual_quantity', 'actual_unit',
            'created_at', 'updated_at',
        ]

    def validate_scheduled_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError('Choose a future pickup time.')
        return value

    def validate(self, attrs):
        allocation = attrs.get('allocation')
        if allocation is not None and allocation.approved_quantity <= 0:
            raise serializers.ValidationError({
                'allocation': 'A pickup requires a positive approved allocation.'
            })
        return attrs


class PickupScheduleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pickup
        fields = [
            'scheduled_at', 'pickup_type', 'pickup_address',
            'contact_person', 'contact_phone', 'notes',
        ]

    def validate_scheduled_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError('Choose a future pickup time.')
        return value


class VolunteerAssignmentSerializer(serializers.Serializer):
    volunteer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True, role='volunteer'),
        required=False,
        allow_null=True,
    )


class PickupCompletionSerializer(serializers.Serializer):
    actual_quantity = serializers.DecimalField(
        max_digits=10, decimal_places=3, min_value=Decimal('0.001')
    )
    actual_unit = serializers.ChoiceField(choices=Donation.UNIT_CHOICES)

    def validate(self, attrs):
        pickup = self.context['pickup']
        if not units_compatible(attrs['actual_unit'], pickup.allocation.approved_unit):
            raise serializers.ValidationError({
                'actual_unit': 'Use a unit compatible with the approved allocation.'
            })
        actual, _ = quantity_in_base(attrs['actual_quantity'], attrs['actual_unit'])
        approved, _ = quantity_in_base(
            pickup.allocation.approved_quantity, pickup.allocation.approved_unit
        )
        if actual > approved:
            raise serializers.ValidationError({
                'actual_quantity': (
                    f'Collected quantity cannot exceed the approved '
                    f'{pickup.allocation.approved_quantity} {pickup.allocation.approved_unit}.'
                )
            })
        return attrs


class PickupFailureSerializer(serializers.Serializer):
    failure_reason = serializers.CharField(
        min_length=5, max_length=2000, trim_whitespace=True
    )
