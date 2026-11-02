import logging
from .models import AuditLog

logger = logging.getLogger('audit')

def log_audit(*, user=None, action, object_type, object_id, object_repr='', changes=None, request=None, critical=False):
    ip_address = None
    user_agent = ''
    if request is not None:
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            object_type=object_type,
            object_id=object_id,
            object_repr=object_repr or '',
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception as exc:
        logger.exception('Audit log failed for %s %s #%s: %s', action, object_type, object_id, exc)
        if critical:
            raise
