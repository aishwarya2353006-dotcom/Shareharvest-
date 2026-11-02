from django.db import models
from django.core.validators import RegexValidator
from accounts.models import User
from organizations.models import Organization
from donations.models import Donation


class OrganizationCompliance(models.Model):
    COMPLIANCE_STATUS_CHOICES = [
        ('pending', 'Pending Submission'),
        ('submitted', 'Submitted for Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name='compliance_record'
    )
    fssai_license_number = models.CharField(
        max_length=50, blank=True,
        validators=[RegexValidator(
            regex=r'^[0-9]{14}$',
            message='FSSAI license number must be 14 digits.'
        )]
    )
    fssai_license_expiry = models.DateField(null=True, blank=True)
    compliance_status = models.CharField(
        max_length=20, choices=COMPLIANCE_STATUS_CHOICES, default='pending'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_compliance_records'
    )
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization_compliance'
        ordering = ['-created_at']

    def __str__(self):
        return f'Compliance for {self.organization.name} ({self.compliance_status})'

    @property
    def is_verified(self):
        return self.compliance_status == 'verified'

    @property
    def license_expired(self):
        if self.fssai_license_expiry:
            from django.utils import timezone
            return self.fssai_license_expiry < timezone.now().date()
        return False


class AllergenDeclaration(models.Model):
    ALLERGEN_CHOICES = [
        ('cereals_containing_gluten', 'Cereals containing gluten'),
        ('crustaceans', 'Crustaceans'),
        ('eggs', 'Eggs'),
        ('fish', 'Fish'),
        ('peanuts', 'Peanuts'),
        ('soybeans', 'Soybeans'),
        ('milk', 'Milk'),
        ('tree_nuts', 'Tree nuts'),
        ('sulphites', 'Sulphites'),
        ('lupin', 'Lupin'),
        ('molluscs', 'Molluscs'),
        ('sesame_seeds', 'Sesame seeds'),
    ]

    DECLARATION_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]

    donation = models.ForeignKey(
        Donation, on_delete=models.CASCADE, related_name='allergen_declarations'
    )
    allergens_present = models.JSONField(default=list, blank=True)
    cross_contamination_risk = models.BooleanField(default=False)
    cross_contamination_details = models.TextField(blank=True)
    declaration_status = models.CharField(
        max_length=20, choices=DECLARATION_STATUS_CHOICES, default='pending'
    )
    declared_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='allergen_declarations'
    )
    declared_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_allergen_declarations'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'allergen_declarations'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['donation'],
                name='unique_allergen_declaration_per_donation',
            ),
        ]

    def __str__(self):
        return f'Allergen declaration for {self.donation.title}'

    @property
    def allergen_list(self):
        return self.allergens_present if isinstance(self.allergens_present, list) else []


class ComplianceDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ('fssai_license', 'FSSAI License'),
        ('food_safety_certificate', 'Food Safety Certificate'),
        ('health_trade_license', 'Health Trade License'),
        ('gst_certificate', 'GST Certificate'),
        ('other', 'Other'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='compliance_documents'
    )
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    file_path = models.CharField(max_length=500)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='uploaded_compliance_documents'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_compliance_documents'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'compliance_documents'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.get_document_type_display()} for {self.organization.name}'
