
from rest_framework import serializers
from .models import Donation


class DonationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    donor_username = serializers.CharField(source='donor.username', read_only=True)
    allergen_declaration = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Donation
        fields = '__all__'
        read_only_fields = ['donor', 'organization', 'quantity_kg', 'published_at', 'created_at', 'updated_at', 'allergen_declaration']

    def get_allergen_declaration(self, obj):
        try:
            from compliance.models import AllergenDeclaration
            declaration = AllergenDeclaration.objects.filter(donation=obj).first()
            if not declaration:
                return None
            return {
                'status': declaration.declaration_status,
                'allergens_present': declaration.allergen_list,
                'cross_contamination_risk': declaration.cross_contamination_risk,
                'cross_contamination_details': declaration.cross_contamination_details,
                'declared_at': declaration.declared_at,
            }
        except Exception:
            return None

    def validate(self, attrs):
        # Ensure quantity is positive if provided
        quantity = attrs.get('quantity')
        if quantity is not None and quantity <= 0:
            raise serializers.ValidationError({'quantity': 'Quantity must be greater than zero.'})
        # Ensure available_from is before available_until if both are provided
        available_from = attrs.get('available_from')
        available_until = attrs.get('available_until')
        if available_from is not None and available_until is not None and available_from >= available_until:
            raise serializers.ValidationError({'available_until': 'Available until must be after available from.'})
        if self.instance is not None and ('quantity' in attrs or 'unit' in attrs):
            from donation_requests.models import DonationRequest
            from donation_requests.services import (
                allocated_quantity_base,
                quantity_in_base,
                units_compatible,
            )

            new_unit = attrs.get('unit', self.instance.unit)
            new_quantity = attrs.get('quantity', self.instance.quantity)
            has_requests = DonationRequest.objects.filter(donation=self.instance).exists()
            if has_requests and not units_compatible(new_unit, self.instance.unit):
                raise serializers.ValidationError({
                    'unit': 'The unit cannot change to an incompatible type after requests exist.'
                })
            new_total, _ = quantity_in_base(new_quantity, new_unit)
            allocated = allocated_quantity_base(self.instance)
            if new_total < allocated:
                raise serializers.ValidationError({
                    'quantity': 'Quantity cannot be lower than the quantity already allocated.'
                })
        return attrs

class BrowseDonationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    donor_username = serializers.CharField(source='donor.username', read_only=True)
    allergen_declaration = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Donation
        exclude = ['pickup_address', 'pickup_instructions']
        read_only_fields = ['donor', 'organization', 'quantity_kg', 'published_at', 'created_at', 'updated_at', 'allergen_declaration']

    def get_allergen_declaration(self, obj):
        try:
            from compliance.models import AllergenDeclaration
            declaration = AllergenDeclaration.objects.filter(donation=obj).first()
            if not declaration:
                return None
            return {
                'status': declaration.declaration_status,
                'allergens_present': declaration.allergen_list,
                'cross_contamination_risk': declaration.cross_contamination_risk,
                'cross_contamination_details': declaration.cross_contamination_details,
                'declared_at': declaration.declared_at,
            }
        except Exception:
            return None
