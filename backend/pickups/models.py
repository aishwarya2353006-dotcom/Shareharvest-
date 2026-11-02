from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from accounts.models import User
from donations.models import Donation
from donation_requests.models import DonationRequest, DonationAllocation


class Pickup(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
        ('failed', 'Failed'),
    ]

    PICKUP_TYPE_CHOICES = [
        ('self', 'Self Pickup'),
        ('volunteer', 'Volunteer Pickup'),
        ('delivery_partner', 'Delivery Partner'),
    ]

    donation = models.ForeignKey(Donation, on_delete=models.CASCADE, related_name='pickups')
    request = models.ForeignKey(DonationRequest, on_delete=models.PROTECT, related_name='pickups')
    allocation = models.ForeignKey(DonationAllocation, on_delete=models.PROTECT, related_name='pickups')
    pickup_type = models.CharField(max_length=20, choices=PICKUP_TYPE_CHOICES)
    scheduled_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    no_show_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    volunteer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_pickups')
    pickup_address = models.TextField()
    contact_person = models.CharField(max_length=255)
    contact_phone = models.CharField(max_length=20)
    notes = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    actual_quantity = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    actual_unit = models.CharField(max_length=10, choices=Donation.UNIT_CHOICES, null=True, blank=True)
    # Kept for backwards compatibility with records created before actual quantities
    # were recorded with their original unit.
    actual_quantity_kg = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pickups'
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['donation', 'status']),
            models.Index(fields=['volunteer', 'status', 'scheduled_at']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['allocation']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['allocation'],
                name='uniq_pickup_per_allocation',
            ),
            models.CheckConstraint(
                check=(
                    Q(actual_quantity__isnull=True, actual_unit__isnull=True)
                    | Q(actual_quantity__isnull=False, actual_unit__isnull=False)
                ),
                name='pickup_actual_quantity_unit_pair',
            ),
            models.CheckConstraint(
                check=Q(actual_quantity__isnull=True) | Q(actual_quantity__gte=0),
                name='pickup_actual_quantity_nonnegative',
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        status='scheduled',
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        no_show_at__isnull=True,
                        failed_at__isnull=True,
                        actual_quantity__isnull=True,
                        actual_unit__isnull=True,
                    )
                    | Q(
                        status='in_progress',
                        started_at__isnull=False,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        no_show_at__isnull=True,
                        failed_at__isnull=True,
                        actual_quantity__isnull=True,
                        actual_unit__isnull=True,
                    )
                    | Q(
                        status='completed',
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        actual_quantity__gt=0,
                        actual_unit__isnull=False,
                        cancelled_at__isnull=True,
                        no_show_at__isnull=True,
                        failed_at__isnull=True,
                    )
                    | Q(
                        status='cancelled',
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        cancelled_at__isnull=False,
                        no_show_at__isnull=True,
                        failed_at__isnull=True,
                        actual_quantity__isnull=True,
                        actual_unit__isnull=True,
                    )
                    | Q(
                        status='no_show',
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        no_show_at__isnull=False,
                        failed_at__isnull=True,
                        actual_quantity__isnull=True,
                        actual_unit__isnull=True,
                    )
                    | Q(
                        status='failed',
                        started_at__isnull=False,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        no_show_at__isnull=True,
                        failed_at__isnull=False,
                        actual_quantity__isnull=True,
                        actual_unit__isnull=True,
                    )
                ),
                name='pickup_status_timestamp_consistency',
            ),
        ]

    def __str__(self):
        return f'Pickup for {self.donation.title} at {self.scheduled_at}'

    def clean(self):
        errors = {}
        if self.allocation_id and self.request_id and self.donation_id:
            if self.allocation.request_id != self.request_id:
                errors['request'] = 'The request must belong to the selected allocation.'
            if self.request.donation_id != self.donation_id:
                errors['donation'] = 'The donation must belong to the selected request.'
            if self.request.status not in ('approved', 'partially_approved'):
                errors['allocation'] = 'A pickup requires an approved allocation.'
            if self.allocation.approved_quantity <= 0:
                errors['allocation'] = 'A pickup requires a positive approved quantity.'
            from donation_requests.services import quantity_in_base, units_compatible
            if not units_compatible(self.allocation.approved_unit, self.request.requested_unit):
                errors['allocation'] = 'The allocation unit is incompatible with its request.'
            if not units_compatible(self.allocation.approved_unit, self.donation.unit):
                errors['allocation'] = 'The allocation unit is incompatible with its donation.'
            if self.actual_quantity is not None and self.actual_unit:
                if not units_compatible(self.actual_unit, self.allocation.approved_unit):
                    errors['actual_unit'] = 'The collected quantity unit must match the allocation dimension.'
                else:
                    actual_base, _ = quantity_in_base(self.actual_quantity, self.actual_unit)
                    approved_base, _ = quantity_in_base(
                        self.allocation.approved_quantity,
                        self.allocation.approved_unit,
                    )
                    if actual_base > approved_base:
                        errors['actual_quantity'] = 'Collected quantity cannot exceed the approved allocation.'
        if self.status == 'completed' and (
            self.actual_quantity is None
            or self.actual_quantity <= 0
            or self.actual_unit is None
        ):
            errors['actual_quantity'] = 'A completed pickup must record a positive collected quantity and its unit.'
        if self.status != 'completed' and (
            self.actual_quantity is not None or self.actual_unit is not None
        ):
            errors['actual_quantity'] = 'Collected quantity can only be recorded when completing a pickup.'
        if self.status == 'failed' and not self.failure_reason.strip():
            errors['failure_reason'] = 'A reason is required when a pickup fails.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)