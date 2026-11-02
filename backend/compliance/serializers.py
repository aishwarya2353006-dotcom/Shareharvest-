from rest_framework import serializers
from .models import OrganizationCompliance, AllergenDeclaration, ComplianceDocument
from organizations.models import Organization
from donations.models import Donation
from accounts.models import User


class OrganizationComplianceSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    verified_by_username = serializers.CharField(source='verified_by.username', read_only=True)

    class Meta:
        model = OrganizationCompliance
        fields = [
            'id', 'organization', 'organization_name', 'fssai_license_number',
            'fssai_license_expiry', 'compliance_status', 'submitted_at',
            'verified_at', 'verified_by', 'verified_by_username',
            'rejection_reason', 'notes', 'is_verified', 'license_expired',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'organization', 'organization_name', 'fssai_license_number',
            'fssai_license_expiry', 'submitted_at', 'compliance_status',
            'verified_at', 'verified_by', 'verified_by_username',
            'rejection_reason', 'is_verified', 'license_expired',
            'created_at', 'updated_at',
        ]

    def validate_fssai_license_number(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError('FSSAI license number must contain only digits.')
        if value and len(value) != 14:
            raise serializers.ValidationError('FSSAI license number must be 14 digits.')
        return value


class OrganizationComplianceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationCompliance
        fields = [
            'fssai_license_number', 'fssai_license_expiry', 'notes',
        ]

    def validate(self, attrs):
        fssai_number = attrs.get('fssai_license_number')
        fssai_expiry = attrs.get('fssai_license_expiry')
        if fssai_number and not fssai_expiry:
            raise serializers.ValidationError({
                'fssai_license_expiry': 'License expiry date is required when a license number is provided.'
            })
        return attrs


class OrganizationComplianceVerifySerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=('verify', 'reject'))
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class AllergenDeclarationSerializer(serializers.ModelSerializer):
    donation_title = serializers.CharField(source='donation.title', read_only=True)
    declared_by_username = serializers.CharField(source='declared_by.username', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)

    class Meta:
        model = AllergenDeclaration
        fields = [
            'id', 'donation', 'donation_title', 'allergens_present',
            'cross_contamination_risk', 'cross_contamination_details',
            'declaration_status', 'declared_by', 'declared_by_username',
            'declared_at', 'reviewed_by', 'reviewed_by_username',
            'reviewed_at', 'review_notes', 'allergen_list',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'donation', 'donation_title', 'declared_by',
            'declared_by_username', 'declared_at', 'reviewed_by',
            'reviewed_by_username', 'reviewed_at', 'allergen_list',
            'created_at', 'updated_at',
        ]

    def validate_allergens_present(self, value):
        valid_allergens = {choice[0] for choice in AllergenDeclaration.ALLERGEN_CHOICES}
        if not isinstance(value, list):
            raise serializers.ValidationError('Allergens must be provided as a list.')
        for allergen in value:
            if allergen not in valid_allergens:
                raise serializers.ValidationError(f'Invalid allergen: {allergen}.')
        return value


class AllergenDeclarationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AllergenDeclaration
        fields = [
            'allergens_present', 'cross_contamination_risk',
            'cross_contamination_details',
        ]


class AllergenDeclarationReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=('verify', 'reject'))
    review_notes = serializers.CharField(required=False, allow_blank=True)


class ComplianceDocumentSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    verified_by_username = serializers.CharField(source='verified_by.username', read_only=True)

    class Meta:
        model = ComplianceDocument
        fields = [
            'id', 'organization', 'organization_name', 'document_type',
            'file_path', 'uploaded_by', 'uploaded_by_username', 'uploaded_at',
            'is_verified', 'verified_at', 'verified_by', 'verified_by_username',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'organization', 'organization_name', 'uploaded_by',
            'uploaded_by_username', 'uploaded_at', 'is_verified',
            'verified_at', 'verified_by', 'verified_by_username',
            'created_at', 'updated_at',
        ]


class ComplianceDocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceDocument
        fields = ['document_type', 'file_path']
