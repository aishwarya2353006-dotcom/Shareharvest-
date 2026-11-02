from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            'id', 'notification_type', 'title', 'message',
            'related_object_id', 'related_object_type', 'is_read',
            'read_at', 'created_at',
        )
        read_only_fields = fields
