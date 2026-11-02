from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import User
from donation_requests.models import DonationAllocation, DonationRequest
from donations.models import Donation
from organizations.models import Membership
from audit.services import log_audit
from .models import Pickup
from .serializers import (
    PickupCompletionSerializer,
    PickupFailureSerializer,
    PickupScheduleUpdateSerializer,
    PickupSerializer,
    VolunteerAssignmentSerializer,
)
from notifications.services import notify_pickup


class PickupConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'The pickup operation conflicts with its current state.'
    default_code = 'pickup_conflict'


def organization_member(user, organization, role):
    return user.role == role and Membership.objects.filter(
        user=user, organization=organization, is_active=True
    ).exists()


def is_party_member(user, pickup):
    return (
        organization_member(user, pickup.donation.organization, 'donor')
        or organization_member(user, pickup.request.organization, 'recipient')
    )


def can_schedule_allocation(user, allocation):
    if user.role == 'admin':
        return True
    request_obj = allocation.request
    return (
        organization_member(user, request_obj.donation.organization, 'donor')
        or organization_member(user, request_obj.organization, 'recipient')
    )


def volunteer_is_eligible(user, request_obj):
    if user.role != 'volunteer' or not user.is_active:
        return False
    return Membership.objects.filter(
        user=user,
        is_active=True,
        role='volunteer',
        organization_id__in=(
            request_obj.donation.organization_id,
            request_obj.organization_id,
        ),
    ).exists()


def can_access_pickup(user, pickup):
    return (
        user.role == 'admin'
        or is_party_member(user, pickup)
        or (
            pickup.volunteer_id == user.pk
            and volunteer_is_eligible(user, pickup.request)
        )
    )


def pickup_queryset_for(user):
    queryset = Pickup.objects.select_related(
        'donation', 'donation__organization', 'request',
        'request__organization', 'allocation', 'volunteer',
    )
    if user.role == 'admin':
        return queryset
    visible = Q(
        donation__organization__memberships__user=user,
        donation__organization__memberships__is_active=True,
    ) if user.role == 'donor' else Q(pk__in=[])
    if user.role == 'recipient':
        visible |= Q(
            request__organization__memberships__user=user,
            request__organization__memberships__is_active=True,
        )
    if user.role == 'volunteer':
        visible |= Q(
            volunteer=user,
            request__donation__organization__memberships__user=user,
            request__donation__organization__memberships__is_active=True,
            request__donation__organization__memberships__role='volunteer',
        ) | Q(
            volunteer=user,
            request__organization__memberships__user=user,
            request__organization__memberships__is_active=True,
            request__organization__memberships__role='volunteer',
        )
    return queryset.filter(visible).distinct()


class PickupViewSet(viewsets.ModelViewSet):
    serializer_class = PickupSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        queryset = pickup_queryset_for(self.request.user)
        pickup_status = self.request.query_params.get('status')
        if pickup_status:
            if pickup_status not in dict(Pickup.STATUS_CHOICES):
                raise ValidationError({'status': 'Unknown pickup status.'})
            queryset = queryset.filter(status=pickup_status)
        return queryset.order_by('scheduled_at', 'id')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allocation_id = serializer.validated_data['allocation'].pk
        try:
            with transaction.atomic():
                allocation_stub = DonationAllocation.objects.select_related(
                    'request', 'request__donation'
                ).get(pk=allocation_id)
                donation = Donation.objects.select_for_update().get(
                    pk=allocation_stub.request.donation_id
                )
                request_obj = DonationRequest.objects.select_for_update().select_related(
                    'organization'
                ).get(pk=allocation_stub.request_id)
                allocation = DonationAllocation.objects.select_for_update().get(
                    pk=allocation_id
                )
                if not can_schedule_allocation(request.user, allocation):
                    raise NotFound('The approved allocation was not found.')
                if request_obj.status not in ('approved', 'partially_approved'):
                    raise ValidationError({
                        'allocation': 'Pickups can only be scheduled for an approved allocation.'
                    })
                if allocation.approved_quantity <= 0:
                    raise ValidationError({
                        'allocation': 'A pickup requires a positive approved allocation.'
                    })
                if Pickup.objects.filter(allocation=allocation).exists():
                    raise PickupConflict('This allocation already has a pickup.')
                pickup = serializer.save(
                    donation=donation,
                    request=request_obj,
                    allocation=allocation,
                    status='scheduled',
                )
                notify_pickup(pickup, 'pickup_scheduled')
                log_audit(
                    user=request.user, action='create', object_type='pickup',
                    object_id=pickup.pk, object_repr=str(pickup),
                    request=request,
                )
        except IntegrityError:
            if Pickup.objects.filter(allocation_id=allocation_id).exists():
                raise PickupConflict('This allocation already has a pickup.')
            raise
        return Response(self.get_serializer(pickup).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        pickup = self.get_object()
        if not can_access_pickup(request.user, pickup):
            raise NotFound()
        if request.user.role != 'admin' and not is_party_member(request.user, pickup):
            raise PermissionDenied('Only an organization member can change pickup scheduling.')
        with transaction.atomic():
            pickup = Pickup.objects.select_for_update().select_related(
                'donation__organization', 'request__organization', 'allocation'
            ).get(pk=pickup.pk)
            if pickup.status != 'scheduled':
                raise PickupConflict('Only scheduled pickups can be rescheduled or edited.')
            serializer = PickupScheduleUpdateSerializer(
                pickup, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            notify_pickup(pickup, 'pickup_rescheduled')
        return Response(self.get_serializer(pickup).data)

    def update(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Use PATCH to update scheduling fields.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Pickups cannot be deleted. Use the cancel action while scheduled.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=['get'], url_path='eligible-allocations')
    def eligible_allocations(self, request):
        allocations = DonationAllocation.objects.select_related(
            'request', 'request__donation', 'request__donation__organization',
            'request__organization', 'request__donation__donor',
        ).filter(
            request__status__in=('approved', 'partially_approved'),
            approved_quantity__gt=0,
            pickups__isnull=True,
        )
        if request.user.role == 'admin':
            pass
        elif request.user.role == 'donor':
            allocations = allocations.filter(
                request__donation__organization__memberships__user=request.user,
                request__donation__organization__memberships__is_active=True,
            )
        elif request.user.role == 'recipient':
            allocations = allocations.filter(
                request__organization__memberships__user=request.user,
                request__organization__memberships__is_active=True,
            )
        else:
            return Response([])
        allocations = allocations.distinct().order_by('created_at', 'id')
        page = self.paginate_queryset(allocations)
        items = page if page is not None else allocations
        data = [{
            'id': allocation.pk,
            'request': allocation.request_id,
            'donation': allocation.request.donation_id,
            'donation_title': allocation.request.donation.title,
            'approved_quantity': allocation.approved_quantity,
            'approved_unit': allocation.approved_unit,
            'donor_organization_name': allocation.request.donation.organization.name,
            'recipient_organization_name': allocation.request.organization.name,
            'pickup_address': allocation.request.donation.pickup_address,
            'contact_person': allocation.request.donation.organization.name,
            'contact_phone': (
                allocation.request.donation.donor.phone
                or allocation.request.donation.organization.phone
            ),
        } for allocation in items]
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='available-volunteers')
    def available_volunteers(self, request):
        try:
            allocation_id = int(request.query_params.get('allocation', ''))
        except ValueError:
            raise ValidationError({'allocation': 'A valid allocation ID is required.'})
        allocation = DonationAllocation.objects.select_related(
            'request', 'request__donation'
        ).filter(pk=allocation_id).first()
        if allocation is None or not can_schedule_allocation(request.user, allocation):
            raise NotFound('The approved allocation was not found.')
        organization_ids = (
            allocation.request.donation.organization_id,
            allocation.request.organization_id,
        )
        volunteer_ids = Membership.objects.filter(
            organization_id__in=organization_ids,
            is_active=True,
            role='volunteer',
            user__is_active=True,
            user__role='volunteer',
        ).values_list('user_id', flat=True)
        volunteers = User.objects.filter(pk__in=volunteer_ids).order_by(
            'username', 'id'
        ).distinct()
        return Response([{
            'id': volunteer.pk,
            'username': volunteer.username,
        } for volunteer in volunteers])

    def _authorize_progress(self, user, pickup):
        if user.role == 'admin' or is_party_member(user, pickup):
            return
        if (
            pickup.volunteer_id == user.pk
            and volunteer_is_eligible(user, pickup.request)
        ):
            return
        raise PermissionDenied('You are not authorized to update this pickup.')

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        pickup = self.get_object()
        self._authorize_progress(request.user, pickup)
        with transaction.atomic():
            pickup = Pickup.objects.select_for_update().select_related(
                'donation__organization', 'request__organization', 'allocation'
            ).get(pk=pickup.pk)
            self._authorize_progress(request.user, pickup)
            if pickup.status != 'scheduled':
                raise PickupConflict('Only scheduled pickups can be started.')
            if pickup.scheduled_at > timezone.now():
                raise ValidationError({'scheduled_at': 'A pickup cannot start before its scheduled time.'})
            pickup.status = 'in_progress'
            pickup.started_at = timezone.now()
            pickup.save(update_fields=['status', 'started_at', 'updated_at'])
            notify_pickup(pickup, 'pickup_started')
            log_audit(
                user=request.user, action='update', object_type='pickup',
                object_id=pickup.pk, object_repr=str(pickup),
                changes={'status': 'in_progress'}, request=request,
            )
        return Response(self.get_serializer(pickup).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        pickup = self.get_object()
        self._authorize_progress(request.user, pickup)
        with transaction.atomic():
            pickup = Pickup.objects.select_for_update().select_related(
                'donation__organization', 'request__organization', 'allocation'
            ).get(pk=pickup.pk)
            self._authorize_progress(request.user, pickup)
            if pickup.status != 'in_progress':
                raise PickupConflict('Only in-progress pickups can be completed.')
            completion = PickupCompletionSerializer(
                data=request.data, context={'pickup': pickup}
            )
            completion.is_valid(raise_exception=True)
            pickup.actual_quantity = completion.validated_data['actual_quantity']
            pickup.actual_unit = completion.validated_data['actual_unit']
            pickup.status = 'completed'
            pickup.completed_at = timezone.now()
            pickup.save(update_fields=[
                'actual_quantity', 'actual_unit', 'status', 'completed_at',
                'updated_at',
            ])
            notify_pickup(pickup, 'pickup_completed')
            log_audit(
                user=request.user, action='update', object_type='pickup',
                object_id=pickup.pk, object_repr=str(pickup),
                changes={'status': 'completed'}, request=request,
            )
        return Response(self.get_serializer(pickup).data)

    @action(detail=True, methods=['post'], url_path='no-show')
    def no_show(self, request, pk=None):
        pickup = self.get_object()
        self._authorize_progress(request.user, pickup)
        with transaction.atomic():
            pickup = Pickup.objects.select_for_update().select_related(
                'donation__organization', 'request__organization', 'allocation'
            ).get(pk=pickup.pk)
            self._authorize_progress(request.user, pickup)
            if pickup.status != 'scheduled':
                raise PickupConflict('Only scheduled pickups can be marked as a no-show.')
            if pickup.scheduled_at > timezone.now():
                raise ValidationError({'scheduled_at': 'A pickup cannot be marked no-show before its scheduled time.'})
            pickup.status = 'no_show'
            pickup.no_show_at = timezone.now()
            pickup.save(update_fields=['status', 'no_show_at', 'updated_at'])
            notify_pickup(pickup, 'pickup_no_show')
        return Response(self.get_serializer(pickup).data)

    @action(detail=True, methods=['post'])
    def fail(self, request, pk=None):
        pickup = self.get_object()
        self._authorize_progress(request.user, pickup)
        with transaction.atomic():
            pickup = Pickup.objects.select_for_update().select_related(
                'donation__organization', 'request__organization', 'allocation'
            ).get(pk=pickup.pk)
            self._authorize_progress(request.user, pickup)
            if pickup.status != 'in_progress':
                raise PickupConflict('Only in-progress pickups can be marked failed.')
            failure = PickupFailureSerializer(data=request.data)
            failure.is_valid(raise_exception=True)
            pickup.status = 'failed'
            pickup.failure_reason = failure.validated_data['failure_reason']
            pickup.failed_at = timezone.now()
            pickup.save(update_fields=[
                'status', 'failure_reason', 'failed_at', 'updated_at',
            ])
            notify_pickup(pickup, 'pickup_failed')
        return Response(self.get_serializer(pickup).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        pickup = self.get_object()
        if request.user.role != 'admin' and not is_party_member(request.user, pickup):
            raise PermissionDenied('Only a donor or recipient organization member can cancel a pickup.')
        with transaction.atomic():
            pickup = Pickup.objects.select_for_update().select_related(
                'donation__organization', 'request__organization', 'allocation'
            ).get(pk=pickup.pk)
            if pickup.status != 'scheduled':
                raise PickupConflict('Only scheduled pickups can be cancelled.')
            pickup.status = 'cancelled'
            pickup.cancelled_at = timezone.now()
            pickup.save(update_fields=['status', 'cancelled_at', 'updated_at'])
            notify_pickup(pickup, 'pickup_cancelled')
            log_audit(
                user=request.user, action='cancel', object_type='pickup',
                object_id=pickup.pk, object_repr=str(pickup),
                request=request,
            )
        return Response(self.get_serializer(pickup).data)

    @action(detail=False, methods=['get'], url_path='claimable')
    def claimable(self, request):
        user = request.user
        if user.role != 'volunteer' or not user.is_active:
            raise PermissionDenied('Only active volunteers can browse claimable pickups.')
        organization_ids = Membership.objects.filter(
            user=user, is_active=True, role='volunteer', user__is_active=True
        ).values_list('organization_id', flat=True)
        queryset = Pickup.objects.select_related(
            'donation', 'donation__organization', 'request',
            'request__organization', 'allocation', 'volunteer',
        ).filter(
            status='scheduled',
            volunteer__isnull=True,
        ).filter(
            Q(donation__organization_id__in=organization_ids)
            | Q(request__organization_id__in=organization_ids)
        ).distinct().order_by('scheduled_at', 'id')
        page = self.paginate_queryset(queryset)
        items = page if page is not None else queryset
        serializer = self.get_serializer(items, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='claim')
    def claim(self, request, pk=None):
        user = request.user
        if user.role != 'volunteer' or not user.is_active:
            raise PermissionDenied('Only active volunteers can claim pickups.')
        with transaction.atomic():
            try:
                pickup = Pickup.objects.select_for_update().select_related(
                    'donation__organization', 'request__organization', 'allocation'
                ).get(pk=pk)
            except Pickup.DoesNotExist:
                raise NotFound('The pickup was not found.')
            if not volunteer_is_eligible(user, pickup.request):
                raise PermissionDenied('You are not eligible to claim this pickup.')
            if pickup.status != 'scheduled' or pickup.volunteer_id is not None:
                raise PickupConflict('This pickup is no longer available to claim.')
            pickup.volunteer = user
            pickup.save(update_fields=['volunteer', 'updated_at'])
            notify_pickup(pickup, 'pickup_volunteer_assigned')
        return Response(self.get_serializer(pickup).data)

    @action(detail=True, methods=['post'], url_path='assign-volunteer')
    def assign_volunteer(self, request, pk=None):
        pickup = self.get_object()
        if request.user.role != 'admin' and not is_party_member(request.user, pickup):
            raise PermissionDenied('Only a donor or recipient organization member can assign a volunteer.')
        body = VolunteerAssignmentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        with transaction.atomic():
            pickup = Pickup.objects.select_for_update().select_related(
                'donation__organization', 'request__organization', 'allocation'
            ).get(pk=pickup.pk)
            if pickup.status != 'scheduled':
                raise PickupConflict('Volunteers can only be assigned to scheduled pickups.')
            volunteer = body.validated_data.get('volunteer')
            if volunteer is not None and not volunteer_is_eligible(volunteer, pickup.request):
                raise ValidationError({
                    'volunteer': (
                        'The volunteer must have an active volunteer membership in '
                        'the donor or recipient organization.'
                    )
                })
            pickup.volunteer = volunteer
            pickup.save(update_fields=['volunteer', 'updated_at'])
            if volunteer is not None:
                notify_pickup(pickup, 'pickup_volunteer_assigned')
        return Response(self.get_serializer(pickup).data)
