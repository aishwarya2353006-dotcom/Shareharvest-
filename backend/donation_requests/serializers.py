from decimal import Decimal

from rest_framework import serializers

from donations.models import Donation
from .models import DonationAllocation, DonationRequest
from .services import (
    UNIT_DIMENSIONS,
    request_allocated_quantity_base,
    request_remaining_base,
    validate_request_values,
)


class DonationAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DonationAllocation
        fields = [
            'id', 'request', 'approved_by', 'approved_quantity', 'approved_unit',
            'approved_quantity_kg', 'notes', 'idempotency_key', 'created_at',
        ]
        read_only_fields = fields


class AllocationCreateSerializer(serializers.Serializer):
    approved_quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01')
    )
    approved_unit = serializers.ChoiceField(choices=Donation.UNIT_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class DonationRequestSerializer(serializers.ModelSerializer):
    approved_quantity = serializers.SerializerMethodField()
    remaining_quantity = serializers.SerializerMethodField()
    allocations = DonationAllocationSerializer(many=True, read_only=True)
    requested_quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01')
    )
    donation = serializers.PrimaryKeyRelatedField(queryset=Donation.objects.all())
    donation_title = serializers.CharField(source='donation.title', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = DonationRequest
        fields = [
            'id', 'recipient', 'organization', 'organization_name', 'donation', 'donation_title', 'requested_quantity',
            'requested_unit', 'requested_quantity_kg', 'status', 'notes',
            'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
            'approved_quantity', 'remaining_quantity', 'allocations',
        ]
        read_only_fields = [
            'id', 'recipient', 'requested_quantity_kg', 'status', 'reviewed_by',
            'reviewed_at', 'created_at', 'updated_at', 'approved_quantity',
            'remaining_quantity', 'allocations',
        ]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields['donation'].read_only = True
            fields['organization'].read_only = True
        return fields

    def validate(self, attrs):
        donation = attrs.get('donation', getattr(self.instance, 'donation', None))
        organization = attrs.get('organization', getattr(self.instance, 'organization', None))
        quantity = attrs.get('requested_quantity', getattr(self.instance, 'requested_quantity', None))
        unit = attrs.get('requested_unit', getattr(self.instance, 'requested_unit', None))
        if donation is None or organization is None or quantity is None or unit is None:
            raise serializers.ValidationError('Donation, organization, quantity, and unit are required.')
        validate_request_values(
            user=self.context['request'].user,
            organization=organization,
            donation=donation,
            quantity=quantity,
            unit=unit,
        )
        return attrs

    def get_approved_quantity(self, obj):
        base_quantity = request_allocated_quantity_base(obj)
        factor = UNIT_DIMENSIONS[obj.requested_unit][1]
        return base_quantity / factor

    def get_remaining_quantity(self, obj):
        base_quantity = request_remaining_base(obj)
        factor = UNIT_DIMENSIONS[obj.requested_unit][1]
        return base_quantity / factor


