from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response

from donations.models import Donation
from organizations.models import Membership
from .models import DonationAllocation, DonationRequest
from .serializers import (
    AllocationCreateSerializer,
    DonationAllocationSerializer,
    DonationRequestSerializer,
)
from .services import (
    allocated_quantity_base,
    donation_remaining_base,
    quantity_in_base,
    request_allocated_quantity_base,
    request_remaining_base,
    units_compatible,
    validate_request_values,
)
from notifications.services import notify_request_reviewed, notify_request_submitted
from audit.services import log_audit


class WorkflowConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'The requested operation conflicts with the current workflow state.'
    default_code = 'conflict'


def active_member(user, organization, roles=None):
    memberships = Membership.objects.filter(
        user=user, organization=organization, is_active=True
    )
    if roles is not None:
        memberships = memberships.filter(role__in=roles)
    return memberships.exists()


def can_manage_donation(user, donation):
    return (
        user.role == 'admin'
        or donation.donor_id == user.pk
        or active_member(user, donation.organization, roles=('owner', 'admin'))
    )


def can_manage_recipient_request(user, donation_request):
    return (
        donation_request.recipient_id == user.pk
        or active_member(
            user,
            donation_request.organization,
            roles=('owner', 'admin'),
        )
    )


def ensure_donation_is_allocatable(donation):
    now = timezone.now()
    if donation.status != 'published':
        raise WorkflowConflict('Only published donations can be allocated.')
    if donation.available_from > now:
        raise WorkflowConflict('This donation is not available yet.')
    if donation.available_until <= now:
        raise WorkflowConflict('This donation has expired.')


class DonationRequestViewSet(viewsets.ModelViewSet):
    serializer_class = DonationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        queryset = DonationRequest.objects.select_related(
            'recipient', 'organization', 'donation', 'donation__organization',
            'donation__donor', 'reviewed_by',
        ).prefetch_related('allocations')
        if user.role == 'admin':
            visible = queryset
        elif user.role == 'recipient':
            # Recipient accounts can only access their own request records.
            visible = queryset.filter(recipient=user)
        else:
            visible = queryset.filter(
                Q(recipient=user)
                | Q(
                    organization__memberships__user=user,
                    organization__memberships__is_active=True,
                    organization__memberships__role__in=('owner', 'admin'),
                )
                | Q(donation__donor=user)
                | Q(
                    donation__organization__memberships__user=user,
                    donation__organization__memberships__is_active=True,
                    donation__organization__memberships__role__in=('owner', 'admin'),
                )
            ).distinct()
        if self.request.query_params.get('mine', '').lower() in {'1', 'true', 'yes'}:
            # A recipient can request a list scoped strictly to their own submissions.
            visible = visible.filter(recipient=user)
        for parameter, field in (
            ('donation', 'donation_id'),
            ('organization', 'organization_id'),
        ):
            value = self.request.query_params.get(parameter)
            if value is not None:
                try:
                    visible = visible.filter(**{field: int(value)})
                except ValueError:
                    raise ValidationError({parameter: 'Must be an integer ID.'})
        request_status = self.request.query_params.get('status')
        if request_status:
            valid_statuses = {choice[0] for choice in DonationRequest.STATUS_CHOICES}
            if request_status not in valid_statuses:
                raise ValidationError({'status': 'Unknown request status.'})
            visible = visible.filter(status=request_status)
        return visible

    def perform_create(self, serializer):
        donation_id = serializer.validated_data['donation'].pk
        with transaction.atomic():
            donation = Donation.objects.select_for_update().get(pk=donation_id)
            organization = serializer.validated_data['organization']
            validate_request_values(
                user=self.request.user,
                organization=organization,
                donation=donation,
                quantity=serializer.validated_data['requested_quantity'],
                unit=serializer.validated_data['requested_unit'],
            )
            duplicate = DonationRequest.objects.filter(
                donation=donation,
                organization=organization,
                status__in=('pending', 'partially_approved'),
            ).exists()
            if duplicate:
                raise WorkflowConflict(
                    'This organization already has an open request for the donation.'
                )
            donation_request = serializer.save(recipient=self.request.user, donation=donation)
            notify_request_submitted(donation_request)
            log_audit(
                user=self.request.user, action='create', object_type='donation_request',
                object_id=donation_request.pk, object_repr=str(donation_request),
                request=self.request,
            )

    def partial_update(self, request, *args, **kwargs):
        current = self.get_object()
        if current.recipient_id != request.user.pk:
            raise PermissionDenied('Only the user who submitted the request can edit it.')
        with transaction.atomic():
            donation = Donation.objects.select_for_update().get(pk=current.donation_id)
            locked_request = DonationRequest.objects.select_for_update().get(pk=current.pk)
            if locked_request.status != 'pending':
                raise WorkflowConflict('Only pending requests can be edited.')
            # Editing must respect the donation's current availability window;
            # partially allocated stock is not a reason to reject a valid edit.
            ensure_donation_is_allocatable(donation)
            serializer = self.get_serializer(
                locked_request, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            validate_request_values(
                user=request.user,
                organization=locked_request.organization,
                donation=donation,
                quantity=serializer.validated_data.get(
                    'requested_quantity', locked_request.requested_quantity
                ),
                unit=serializer.validated_data.get(
                    'requested_unit', locked_request.requested_unit
                ),
            )
            serializer.save()
        return Response(self.get_serializer(locked_request).data)

    def update(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Use PATCH to edit a pending request.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Requests are not deleted. Use the cancel action while pending.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        initial = self.get_object()
        body = AllocationCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        idempotency_key = request.headers.get('Idempotency-Key', '').strip()
        if not idempotency_key:
            raise ValidationError({'Idempotency-Key': 'This header is required for approvals.'})
        if len(idempotency_key) > 64:
            raise ValidationError({'Idempotency-Key': 'Must be at most 64 characters.'})
        with transaction.atomic():
            # Lock the shared inventory row first so approvals for separate
            # requests on one donation serialize on databases with row locks.
            donation = Donation.objects.select_for_update().get(pk=initial.donation_id)
            request_obj = DonationRequest.objects.select_for_update().select_related(
                'donation', 'organization'
            ).get(pk=initial.pk)
            if not can_manage_donation(request.user, donation):
                raise PermissionDenied('You cannot approve requests for this donation.')
            prior_allocation = DonationAllocation.objects.filter(
                request=request_obj, idempotency_key=idempotency_key
            ).first()
            if prior_allocation is not None:
                same_operation = (
                    prior_allocation.approved_by_id == request.user.pk
                    and prior_allocation.approved_quantity == body.validated_data['approved_quantity']
                    and prior_allocation.approved_unit == body.validated_data['approved_unit']
                    and prior_allocation.notes == body.validated_data.get('notes', '')
                )
                if not same_operation:
                    raise WorkflowConflict(
                        'This idempotency key was already used for a different allocation.'
                    )
                return Response(self.get_serializer(request_obj).data, status=status.HTTP_200_OK)
            if request_obj.status not in ('pending', 'partially_approved'):
                raise WorkflowConflict('Only pending or partially approved requests can receive allocations.')
            ensure_donation_is_allocatable(donation)

            quantity = body.validated_data['approved_quantity']
            unit = body.validated_data['approved_unit']
            if not units_compatible(unit, donation.unit) or not units_compatible(
                unit, request_obj.requested_unit
            ):
                raise ValidationError({
                    'approved_unit': 'The allocation unit must be compatible with both the donation and request.'
                })

            allocation_base, _ = quantity_in_base(quantity, unit)
            if allocation_base <= 0:
                raise ValidationError({'approved_quantity': 'Quantity must be greater than zero.'})
            if allocation_base > request_remaining_base(request_obj):
                raise WorkflowConflict('Allocation exceeds the quantity still requested.')
            if allocation_base > donation_remaining_base(donation):
                raise WorkflowConflict('Allocation exceeds the donation quantity still available.')

            allocation_notes = body.validated_data.get('notes', '')
            allocation = DonationAllocation.objects.create(
                request=request_obj,
                approved_by=request.user,
                approved_quantity=quantity,
                approved_unit=unit,
                notes=allocation_notes,
                idempotency_key=idempotency_key,
            )
            if request_remaining_base(request_obj) == 0:
                request_obj.status = 'approved'
            else:
                request_obj.status = 'partially_approved'
            request_obj.reviewed_by = request.user
            request_obj.reviewed_at = timezone.now()
            request_obj.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
            notify_request_reviewed(
                request_obj, approved=True, allocation_id=allocation.pk
            )
            log_audit(
                user=request.user, action='approve', object_type='donation_request',
                object_id=request_obj.pk, object_repr=str(request_obj),
                request=request,
            )

            donation_total, _ = quantity_in_base(donation.quantity, donation.unit)
            if allocated_quantity_base(donation) >= donation_total:
                donation.status = 'reserved'
                donation.save(update_fields=['status', 'updated_at'])

        return Response(self.get_serializer(request_obj).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        initial = self.get_object()
        with transaction.atomic():
            donation = Donation.objects.select_for_update().get(pk=initial.donation_id)
            request_obj = DonationRequest.objects.select_for_update().get(pk=initial.pk)
            if not can_manage_donation(request.user, donation):
                raise PermissionDenied('You cannot reject requests for this donation.')
            if request_obj.status != 'pending':
                raise WorkflowConflict('Only pending requests can be rejected.')
            request_obj.status = 'rejected'
            request_obj.reviewed_by = request.user
            request_obj.reviewed_at = timezone.now()
            request_obj.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
            notify_request_reviewed(request_obj, approved=False)
            log_audit(
                user=request.user, action='reject', object_type='donation_request',
                object_id=request_obj.pk, object_repr=str(request_obj),
                request=request,
            )
        return Response(self.get_serializer(request_obj).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        initial = self.get_object()
        with transaction.atomic():
            donation = Donation.objects.select_for_update().get(pk=initial.donation_id)
            request_obj = DonationRequest.objects.select_for_update().get(pk=initial.pk)
            if not can_manage_recipient_request(request.user, request_obj):
                raise PermissionDenied('You cannot cancel this request.')
            if request_obj.status != 'pending':
                raise WorkflowConflict('Only pending requests can be cancelled.')
            request_obj.status = 'cancelled'
            request_obj.save(update_fields=['status', 'updated_at'])
            log_audit(
                user=request.user, action='cancel', object_type='donation_request',
                object_id=request_obj.pk, object_repr=str(request_obj),
                request=request,
            )
        return Response(self.get_serializer(request_obj).data)


class DonationAllocationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DonationAllocationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = DonationAllocation.objects.select_related(
            'request', 'request__recipient', 'request__organization',
            'request__donation', 'request__donation__organization', 'approved_by',
        )
        if user.role == 'admin':
            return queryset
        if user.role == 'recipient':
            return queryset.filter(request__recipient=user)
        return queryset.filter(
            Q(request__recipient=user)
            | Q(request__organization__memberships__user=user,
                request__organization__memberships__is_active=True,
                request__organization__memberships__role__in=('owner', 'admin'))
            | Q(request__donation__donor=user)
            | Q(request__donation__organization__memberships__user=user,
                request__donation__organization__memberships__is_active=True,
                request__donation__organization__memberships__role__in=('owner', 'admin'))
        ).distinct()
