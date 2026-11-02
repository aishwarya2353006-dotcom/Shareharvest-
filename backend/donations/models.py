from django.db import models
from accounts.models import User
from organizations.models import Organization


class Donation(models.Model):
    FOOD_CATEGORY_CHOICES = [
        ('prepared', 'Prepared Meals'),
        ('produce', 'Fresh Produce'),
        ('dairy', 'Dairy & Eggs'),
        ('bakery', 'Bakery Items'),
        ('packaged', 'Packaged Foods'),
        ('beverages', 'Beverages'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('reserved', 'Reserved'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    UNIT_CHOICES = [
        ('kg', 'Kilograms'),
        ('g', 'Grams'),
        ('l', 'Liters'),
        ('ml', 'Milliliters'),
        ('units', 'Units/Items'),
        ('boxes', 'Boxes'),
        ('trays', 'Trays'),
    ]

    MASS_UNITS = {'kg', 'g'}
    VOLUME_UNITS = {'l', 'ml'}
    COUNT_UNITS = {'units', 'boxes', 'trays'}

    donor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='donations')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='donations')
    title = models.CharField(max_length=255)
    description = models.TextField()
    food_category = models.CharField(max_length=20, choices=FOOD_CATEGORY_CHOICES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    quantity_kg = models.DecimalField(max_digits=10, decimal_places=3, editable=False)
    available_from = models.DateTimeField()
    available_until = models.DateTimeField()
    pickup_address = models.TextField()
    pickup_instructions = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'donations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'available_until']),
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['donor', 'created_at']),
            models.Index(fields=['food_category']),
        ]

    def __str__(self):
        return self.title

    @property
    def allocated_quantity_kg(self):
        """Total approved allocation quantity in kg across all allocations."""
        from donation_requests.models import DonationAllocation
        return DonationAllocation.objects.filter(
            request__donation=self,
            request__status__in=['approved', 'partially_approved']
        ).aggregate(total=models.Sum('approved_quantity_kg'))['total'] or 0

    @property
    def available_quantity_kg(self):
        """Remaining available quantity in kg."""
        return self.quantity_kg - self.allocated_quantity_kg

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be greater than zero.'})
        if self.available_from >= self.available_until:
            raise ValidationError({'available_until': 'Available until must be after available from.'})

    def save(self, *args, **kwargs):
        # Normalize quantity to kg
        self.quantity_kg = self._convert_to_kg(self.quantity, self.unit)
        # Set published_at when status changes to published
        if self.pk:
            try:
                old = Donation.objects.get(pk=self.pk)
                if old.status != 'published' and self.status == 'published':
                    from django.utils import timezone
                    self.published_at = timezone.now()
            except Donation.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    def _convert_to_kg(self, quantity, unit):
        """Convert quantity to kg. Raises ValueError for incompatible units."""
        from decimal import Decimal
        q = Decimal(str(quantity))
        if unit == 'kg':
            return q
        elif unit == 'g':
            return q / Decimal('1000')
        elif unit == 'l':
            # Volume units - cannot convert to mass without density
            # Store as-is for volume tracking
            return q
        elif unit == 'ml':
            return q / Decimal('1000')
        elif unit in self.COUNT_UNITS:
            # Count-based units - treat as 1kg per unit for reporting
            return q
        else:
            raise ValueError(f'Unsupported unit: {unit}')

    @classmethod
    def _units_compatible(cls, unit1, unit2):
        """Check if two units are compatible (both mass, both volume, or both count)."""
        return (
            (unit1 in cls.MASS_UNITS and unit2 in cls.MASS_UNITS) or
            (unit1 in cls.VOLUME_UNITS and unit2 in cls.VOLUME_UNITS) or
            (unit1 in cls.COUNT_UNITS and unit2 in cls.COUNT_UNITS)
        )