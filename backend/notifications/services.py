from organizations.models import Membership
from .models import Notification


def create_notification(*, recipient_id, notification_type, title, message,
                        related_object, deduplication_key):
    """Create one durable notification per recipient and source event."""
    if not recipient_id:
        return None
    notification, _ = Notification.objects.get_or_create(
        recipient_id=recipient_id,
        deduplication_key=deduplication_key,
        defaults={
            'notification_type': notification_type,
            'title': title,
            'message': message,
            'related_object_id': related_object.pk,
            'related_object_type': related_object._meta.model_name,
        },
    )
    return notification


def _deliver(recipients, *, event, title, message, related_object, event_key):
    for recipient_id in recipients:
        create_notification(
            recipient_id=recipient_id,
            notification_type=event,
            title=title,
            message=message,
            related_object=related_object,
            deduplication_key=f'{event_key}:{recipient_id}',
        )


def notify_request_submitted(donation_request):
    donation = donation_request.donation
    recipient_ids = {donation.donor_id}
    if donation.organization_id:
        recipient_ids.update(Membership.objects.filter(
            organization_id=donation.organization_id,
            is_active=True,
            role__in=('owner', 'admin'),
            user__is_active=True,
        ).values_list('user_id', flat=True))
    recipient_ids.discard(donation_request.recipient_id)
    _deliver(
        recipient_ids,
        event='request_received',
        title='New donation request',
        message=f'{donation_request.organization.name} requested food from {donation.title}.',
        related_object=donation_request,
        event_key=f'request:{donation_request.pk}:submitted',
    )


def notify_request_reviewed(donation_request, *, approved, allocation_id=None):
    _deliver(
        (donation_request.recipient_id,),
        event='request_approved' if approved else 'request_rejected',
        title='Request approved' if approved else 'Request declined',
        message=(
            f'Your request for {donation_request.donation.title} was approved.'
            if approved else
            f'Your request for {donation_request.donation.title} was declined.'
        ),
        related_object=donation_request,
        event_key=(f'request:{donation_request.pk}:allocation:{allocation_id}' if approved
                   else f'request:{donation_request.pk}:rejected'),
    )


PICKUP_EVENTS = {
    'pickup_scheduled': ('Pickup scheduled', 'A pickup has been scheduled.'),
    'pickup_rescheduled': ('Pickup rescheduled', 'The pickup time or details have changed.'),
    'pickup_started': ('Pickup started', 'The pickup is now in progress.'),
    'pickup_completed': ('Pickup completed', 'The pickup has been completed.'),
    'pickup_cancelled': ('Pickup cancelled', 'The scheduled pickup was cancelled.'),
    'pickup_failed': ('Pickup failed', 'The pickup could not be completed.'),
    'pickup_no_show': ('Pickup missed', 'The scheduled pickup was marked as missed.'),
    'pickup_volunteer_assigned': ('Volunteer assigned', 'A volunteer has been assigned to the pickup.'),
}


def notify_pickup(pickup, event, *, event_key=None):
    title, message = PICKUP_EVENTS[event]
    request = pickup.request
    donation = pickup.donation
    recipients = set(Membership.objects.filter(
        organization_id=donation.organization_id,
        is_active=True,
        role__in=('owner', 'admin', 'member'),
        user__is_active=True,
        user__role='donor',
    ).values_list('user_id', flat=True))
    recipients.update(Membership.objects.filter(
        organization_id=request.organization_id,
        is_active=True,
        role__in=('owner', 'admin', 'member'),
        user__is_active=True,
        user__role='recipient',
    ).values_list('user_id', flat=True))
    if pickup.volunteer_id and Membership.objects.filter(
        user_id=pickup.volunteer_id,
        user__is_active=True,
        user__role='volunteer',
        is_active=True,
        role='volunteer',
        organization_id__in=(donation.organization_id, request.organization_id),
    ).exists():
        recipients.add(pickup.volunteer_id)
    _deliver(
        recipients,
        event=event,
        title=title,
        message=message,
        related_object=pickup,
        event_key=event_key or f'pickup:{pickup.pk}:{event}',
    )
