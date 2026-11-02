from django.db import models
from accounts.models import User


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ('donation_created', 'New Donation Available'),
        ('request_received', 'Request Received'),
        ('request_approved', 'Request Approved'),
        ('request_rejected', 'Request Rejected'),
        ('pickup_scheduled', 'Pickup Scheduled'),
        ('pickup_rescheduled', 'Pickup Rescheduled'),
        ('pickup_started', 'Pickup Started'),
        ('pickup_completed', 'Pickup Completed'),
        ('pickup_cancelled', 'Pickup Cancelled'),
        ('pickup_failed', 'Pickup Failed'),
        ('pickup_no_show', 'Pickup Missed'),
        ('pickup_volunteer_assigned', 'Volunteer Assigned'),
        ('organization_verified', 'Organization Verified'),
        ('system', 'System Notification'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object_type = models.CharField(max_length=50, blank=True)
    deduplication_key = models.CharField(max_length=200, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'deduplication_key'],
                name='notification_recipient_dedup_key_unique',
            ),
        ]

    def __str__(self):
        return f'{self.notification_type} - {self.recipient.username}'
