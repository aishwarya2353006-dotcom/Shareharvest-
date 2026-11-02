from decimal import Decimal

from django.db import models
from accounts.models import User
from organizations.models import Organization
from donations.models import Donation


class DonationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('partially_approved', 'Partially Approved'),
        ('cancelled', 'Cancelled'),
    ]

    UNIT_CHOICES = Donation.UNIT_CHOICES

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='requests')
    donation = models.ForeignKey(Donation, on_delete=models.CASCADE, related_name='requests')
    requested_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    requested_unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    requested_quantity_kg = models.DecimalField(max_digits=10, decimal_places=3, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'donation_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['donation', 'status']),
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['organization', 'status']),
        ]

    def __str__(self):
        return f'Request for {self.donation.title} by {self.recipient.username}'

    @property
    def approved_quantity_kg(self):
        """Total approved quantity in kg across all allocations."""
        return self.allocations.aggregate(
            total=models.Sum('approved_quantity_kg')
        )['total'] or 0

    @property
    def approved_quantity(self):
        """Total approved quantity in requested unit (approximate)."""
        if self.requested_quantity_kg and self.approved_quantity_kg:
            return (
                self.requested_quantity
                * self.approved_quantity_kg
                / self.requested_quantity_kg
            ).quantize(Decimal('0.01'))
        return Decimal('0.00')

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.requested_quantity <= 0:
            raise ValidationError({'requested_quantity': 'Quantity must be greater than zero.'})
        # Validate unit compatibility with donation
        if self.donation_id and self.requested_unit:
            if not self._units_compatible(self.donation.unit, self.requested_unit):
                raise ValidationError({
                    'requested_unit': f'Unit {self.requested_unit} is not compatible with donation unit {self.donation.unit}.'
                })

    def save(self, *args, **kwargs):
        # Normalize quantity to kg
        self.requested_quantity_kg = self._convert_to_kg(self.requested_quantity, self.requested_unit)
        super().save(*args, **kwargs)

    def _units_compatible(self, unit1, unit2):
        """Check if two units are compatible (both mass or both volume)."""
        mass_units = {'kg', 'g'}
        volume_units = {'l', 'ml'}
        unit_units = {'units', 'boxes', 'trays'}
        return (
            (unit1 in mass_units and unit2 in mass_units) or
            (unit1 in volume_units and unit2 in volume_units) or
            (unit1 in unit_units and unit2 in unit_units)
        )

    def _convert_to_kg(self, quantity, unit):
        """Convert quantity to kg. Raises ValueError for incompatible units."""
        from decimal import Decimal
        q = Decimal(str(quantity))
        if unit == 'kg':
            return q
        elif unit == 'g':
            return q / Decimal('1000')
        elif unit == 'l':
            # Cannot convert volume to mass without density - return as-is for volume tracking
            return q
        elif unit == 'ml':
            return q / Decimal('1000')
        elif unit in ('units', 'boxes', 'trays'):
            # Count-based units - treat as 1kg per unit for reporting
            return q
        else:
            raise ValueError(f'Unsupported unit: {unit}')


class DonationAllocation(models.Model):
    """Individual approval action (full or partial) for a donation request."""
    request = models.ForeignKey(DonationRequest, on_delete=models.CASCADE, related_name='allocations')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_allocations')
    approved_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    approved_unit = models.CharField(max_length=10, choices=DonationRequest.UNIT_CHOICES)
    approved_quantity_kg = models.DecimalField(max_digits=10, decimal_places=3, editable=False)
    notes = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'donation_allocations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['request']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['request', 'idempotency_key'],
                name='uniq_allocation_idempotency_per_request',
            ),
        ]

    def __str__(self):
        return f'Allocation of {self.approved_quantity} {self.approved_unit} for request #{self.request_id}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.approved_quantity <= 0:
            raise ValidationError({'approved_quantity': 'Quantity must be greater than zero.'})
        # Validate unit compatibility with request
        if self.request_id and self.approved_unit:
            if not self.request._units_compatible(self.request.requested_unit, self.approved_unit):
                raise ValidationError({
                    'approved_unit': f'Unit {self.approved_unit} is not compatible with request unit {self.request.requested_unit}.'
                })

    def save(self, *args, **kwargs):
        # Normalize quantity to kg
        self.approved_quantity_kg = self.request._convert_to_kg(self.approved_quantity, self.approved_unit)
        super().save(*args, **kwargs)
