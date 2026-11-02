from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role != 'admin':
            raise PermissionDenied('Only platform administrators can view audit logs.')
        queryset = AuditLog.objects.select_related('user').all()
        object_type = self.request.query_params.get('object_type')
        if object_type:
            queryset = queryset.filter(object_type=object_type)
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        return queryset.order_by('-created_at')

