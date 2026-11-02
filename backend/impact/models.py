from django.db import models
from accounts.models import User
from organizations.models import Organization
from donations.models import Donation


class ImpactReport(models.Model):
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Range'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='impact_reports')
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='generated_reports')
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    total_donations = models.PositiveIntegerField(default=0)
    total_quantity_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_recipients_served = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'impact_reports'
        ordering = ['-created_at']

    def __str__(self):
        return f'Impact Report for {self.organization.name} ({self.start_date} to {self.end_date})'


class DonationStatistic(models.Model):
    date = models.DateField()
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='daily_stats')
    donations_count = models.PositiveIntegerField(default=0)
    quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    requests_count = models.PositiveIntegerField(default=0)
    completed_pickups = models.PositiveIntegerField(default=0)
    allocated_quantity_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'donation_statistics'
        unique_together = ['date', 'organization']
        ordering = ['-date']

    def __str__(self):
        return f'Stats for {self.organization.name} on {self.date}'