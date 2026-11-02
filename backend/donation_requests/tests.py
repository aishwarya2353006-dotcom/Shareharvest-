from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from unittest import skipUnless
from uuid import uuid4

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from donations.models import Donation
from donation_requests.models import DonationAllocation, DonationRequest
from organizations.models import Membership, Organization


class DonationRequestWorkflowTests(APITestCase):
    def setUp(self):
        now = timezone.now()
        self.donor = User.objects.create_user(
            username='donor', password='pass', role='donor'
        )
        self.recipient = User.objects.create_user(
            username='recipient', password='pass', role='recipient'
        )
        self.other_recipient = User.objects.create_user(
            username='other-recipient', password='pass', role='recipient'
        )
        self.outsider = User.objects.create_user(
            username='outsider', password='pass', role='recipient'
        )
        self.donor_org = self.make_org('Donor org', 'restaurant')
        self.recipient_org = self.make_org('Recipient org', 'ngo')
        self.other_recipient_org = self.make_org('Other recipient org', 'community')
        Membership.objects.create(user=self.donor, organization=self.donor_org, role='owner')
        Membership.objects.create(user=self.recipient, organization=self.recipient_org, role='member')
        Membership.objects.create(
            user=self.other_recipient,
            organization=self.other_recipient_org,
            role='admin',
        )
        self.donation = Donation.objects.create(
            donor=self.donor,
            organization=self.donor_org,
            title='Fresh produce',
            description='Available produce',
            food_category='produce',
            quantity=Decimal('5.00'),
            unit='kg',
            available_from=now - timedelta(hours=1),
            available_until=now + timedelta(days=1),
            pickup_address='1 Market Road',
            status='published',
        )
        self.client.force_authenticate(user=self.recipient)

    def make_org(self, name, org_type, *, org_status='verified'):
        return Organization.objects.create(
            name=name,
            org_type=org_type,
            address='1 Community Road',
            city='Town',
            state='State',
            postal_code='12345',
            country='USA',
            phone='555-0100',
            email=f'{name.lower().replace(" ", "-")}@example.test',
            status=org_status,
        )

    def request_payload(self, *, organization=None, quantity='4.00', unit='kg'):
        return {
            'donation': self.donation.pk,
            'organization': (organization or self.recipient_org).pk,
            'requested_quantity': quantity,
            'requested_unit': unit,
            'notes': 'Community kitchen request',
        }

    def create_request(self, *, user=None, **kwargs):
        if user is not None:
            self.client.force_authenticate(user=user)
        return self.client.post(
            '/api/donation-requests/', self.request_payload(**kwargs), format='json'
        )

    def allocate(self, request_id, quantity, unit='kg', *, user=None, idempotency_key=None):
        if user is not None:
            self.client.force_authenticate(user=user)
        return self.client.post(
            f'/api/donation-requests/{request_id}/approve/',
            {'approved_quantity': quantity, 'approved_unit': unit},
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key or uuid4().hex,
        )

    def test_recipient_member_can_create_request_and_donor_can_review(self):
        response = self.create_request()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(response.data['recipient'], self.recipient.pk)

        self.client.force_authenticate(user=self.donor)
        listed = self.client.get('/api/donation-requests/')
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data['count'], 1)

    def test_recipient_sees_donor_allocation_status_in_own_request_list(self):
        created = self.create_request(quantity='2.00')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        request_id = created.data['id']

        own_requests = self.client.get('/api/donation-requests/?mine=true')
        self.assertEqual(own_requests.status_code, status.HTTP_200_OK)
        self.assertEqual(own_requests.data['count'], 1)
        self.assertEqual(own_requests.data['results'][0]['status'], 'pending')

        self.client.force_authenticate(user=self.donor)
        donor_requests = self.client.get(
            f'/api/donation-requests/?donation={self.donation.pk}'
        )
        self.assertEqual(donor_requests.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['id'] for item in donor_requests.data['results']], [request_id]
        )
        approved = self.allocate(request_id, '2.00', user=self.donor)
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)
        self.assertEqual(approved.data['status'], 'approved')

        self.client.force_authenticate(user=self.recipient)
        refreshed = self.client.get('/api/donation-requests/?mine=true')
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertEqual(refreshed.data['count'], 1)
        recipient_view = refreshed.data['results'][0]
        self.assertEqual(recipient_view['id'], request_id)
        self.assertEqual(recipient_view['status'], 'approved')
        self.assertEqual(Decimal(recipient_view['approved_quantity']), Decimal('2'))
        self.assertEqual(Decimal(recipient_view['remaining_quantity']), Decimal('0'))
        self.assertEqual(len(recipient_view['allocations']), 1)

    def test_nonmember_and_nonrecipient_cannot_create_request(self):
        self.client.force_authenticate(user=self.outsider)
        response = self.create_request()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        donor_org_recipient = User.objects.create_user(
            username='wrong-role', password='pass', role='donor'
        )
        Membership.objects.create(
            user=donor_org_recipient, organization=self.other_recipient_org, role='member'
        )
        self.client.force_authenticate(user=donor_org_recipient)
        response = self.create_request(organization=self.other_recipient_org)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unverified_or_wrong_type_recipient_organization_is_rejected(self):
        pending_org = self.make_org('Pending NGO', 'ngo', org_status='pending')
        Membership.objects.create(user=self.recipient, organization=pending_org, role='member')
        response = self.create_request(organization=pending_org)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        restaurant = self.make_org('Recipient restaurant', 'restaurant')
        Membership.objects.create(user=self.recipient, organization=restaurant, role='member')
        response = self.create_request(organization=restaurant)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_quantity_must_be_positive_compatible_and_within_available_stock(self):
        for quantity, unit in [('0', 'kg'), ('5.01', 'kg'), ('1', 'l')]:
            response = self.create_request(quantity=quantity, unit=unit)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mass_subunits_are_converted_without_using_legacy_kg_field(self):
        response = self.create_request(quantity='750', unit='g')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        request_obj = DonationRequest.objects.get(pk=response.data['id'])
        self.assertEqual(request_obj.requested_quantity, Decimal('750'))
        self.assertEqual(request_obj.requested_unit, 'g')

    def test_fully_allocated_donation_cannot_be_requested(self):
        first = self.create_request(quantity='5.00')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        allocated = self.allocate(first.data['id'], '5.00', user=self.donor)
        self.assertEqual(allocated.status_code, status.HTTP_200_OK, allocated.data)
        second = self.create_request(quantity='0.01')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST, second.data)


    def test_expired_and_not_yet_available_donations_cannot_be_requested(self):
        pending = self.create_request()
        self.assertEqual(pending.status_code, status.HTTP_201_CREATED)
        self.donation.available_until = timezone.now() - timedelta(minutes=1)
        self.donation.save()
        response = self.create_request()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        expired_approval = self.allocate(
            pending.data['id'], '1.00', user=self.donor
        )
        self.assertEqual(expired_approval.status_code, status.HTTP_409_CONFLICT)

        self.donation.available_until = timezone.now() + timedelta(days=1)
        self.donation.available_from = timezone.now() + timedelta(hours=1)
        self.donation.save()
        response = self.create_request()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_rejected_when_donation_expired_or_not_yet_available(self):
        created = self.create_request()
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        request_id = created.data['id']

        self.donation.available_until = timezone.now() - timedelta(minutes=1)
        self.donation.save()
        expired_edit = self.client.patch(
            f'/api/donation-requests/{request_id}/',
            {'requested_quantity': '3.00'}, format='json',
        )
        self.assertEqual(expired_edit.status_code, status.HTTP_409_CONFLICT, expired_edit.data)
        self.donation.refresh_from_db()
        self.assertEqual(DonationRequest.objects.get(pk=request_id).requested_quantity, Decimal('4.00'))

        self.donation.available_until = timezone.now() + timedelta(days=1)
        self.donation.available_from = timezone.now() + timedelta(hours=1)
        self.donation.save()
        future_edit = self.client.patch(
            f'/api/donation-requests/{request_id}/',
            {'requested_quantity': '3.00'}, format='json',
        )
        self.assertEqual(future_edit.status_code, status.HTTP_409_CONFLICT, future_edit.data)

    def test_edit_allowed_while_donation_partially_allocated_to_others(self):
        created = self.create_request(quantity='2.00')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        request_id = created.data['id']

        # A different request consumes part of the donation's stock.
        other = self.create_request(
            user=self.other_recipient, organization=self.other_recipient_org, quantity='1.00'
        )
        self.assertEqual(other.status_code, status.HTTP_201_CREATED, other.data)
        allocated = self.allocate(other.data['id'], '1.00', user=self.donor)
        self.assertEqual(allocated.status_code, status.HTTP_200_OK, allocated.data)

        self.client.force_authenticate(user=self.recipient)
        # Editing within the still-available stock must not be rejected merely
        # because some of the donation has already been allocated.
        edited = self.client.patch(
            f'/api/donation-requests/{request_id}/',
            {'requested_quantity': '3.00'}, format='json',
        )
        self.assertEqual(edited.status_code, status.HTTP_200_OK, edited.data)
        self.assertEqual(Decimal(edited.data['requested_quantity']), Decimal('3.00'))

    def test_requester_and_donor_isolation(self):
        response = self.create_request()
        request_id = response.data['id']
        self.client.force_authenticate(user=self.outsider)
        self.assertEqual(
            self.client.get(f'/api/donation-requests/{request_id}/').status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/donation-requests/{request_id}/',
                {'notes': 'changed'}, format='json',
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_recipient_member_cannot_read_another_members_request_or_allocation(self):
        Membership.objects.create(
            user=self.other_recipient, organization=self.recipient_org, role='member'
        )
        other_request = DonationRequest.objects.create(
            recipient=self.other_recipient,
            organization=self.recipient_org,
            donation=self.donation,
            requested_quantity=Decimal('1.00'),
            requested_unit='kg',
        )
        DonationAllocation.objects.create(
            request=other_request,
            approved_by=self.donor,
            approved_quantity=Decimal('0.50'),
            approved_unit='kg',
            idempotency_key=uuid4().hex,
        )

        self.client.force_authenticate(user=self.recipient)
        requests_response = self.client.get('/api/donation-requests/')
        allocations_response = self.client.get('/api/allocations/')
        self.assertEqual(requests_response.status_code, status.HTTP_200_OK)
        self.assertEqual(allocations_response.status_code, status.HTTP_200_OK)
        self.assertEqual(requests_response.data['count'], 0)
        self.assertEqual(allocations_response.data['count'], 0)

    def test_mine_list_filter_excludes_other_recipients_in_same_organization(self):
        own = self.create_request()
        other = self.create_request(
            user=self.other_recipient, organization=self.other_recipient_org, quantity='1.00'
        )
        self.assertEqual(own.status_code, status.HTTP_201_CREATED)
        self.assertEqual(other.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=self.recipient)
        response = self.client.get('/api/donation-requests/?mine=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], own.data['id'])

    def test_partial_allocations_complete_request_and_are_read_only(self):
        request_response = self.create_request(quantity='4.00')
        request_id = request_response.data['id']

        self.client.force_authenticate(user=self.donor)
        missing_key = self.client.post(
            f'/api/donation-requests/{request_id}/approve/',
            {'approved_quantity': '1.00', 'approved_unit': 'kg'},
            format='json',
        )
        self.assertEqual(missing_key.status_code, status.HTTP_400_BAD_REQUEST)

        first_key = uuid4().hex
        partial = self.allocate(
            request_id, '1.00', user=self.donor, idempotency_key=first_key
        )
        self.assertEqual(partial.status_code, status.HTTP_200_OK, partial.data)
        self.assertEqual(partial.data['status'], 'partially_approved')
        self.assertEqual(Decimal(partial.data['approved_quantity']), Decimal('1'))
        self.assertEqual(Decimal(partial.data['remaining_quantity']), Decimal('3'))
        self.assertEqual(len(partial.data['allocations']), 1)
        request_obj = DonationRequest.objects.get(pk=request_id)
        self.assertEqual(request_obj.approved_quantity, Decimal('1.00'))
        self.assertEqual(
            self.client.post(
                f'/api/donation-requests/{request_id}/reject/', {}, format='json'
            ).status_code,
            status.HTTP_409_CONFLICT,
        )
        self.client.force_authenticate(user=self.recipient)
        self.assertEqual(
            self.client.post(
                f'/api/donation-requests/{request_id}/cancel/', {}, format='json'
            ).status_code,
            status.HTTP_409_CONFLICT,
        )
        retry = self.allocate(
            request_id, '1.00', user=self.donor, idempotency_key=first_key
        )
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        self.assertEqual(DonationAllocation.objects.filter(request_id=request_id).count(), 1)
        key_conflict = self.allocate(
            request_id, '2.00', user=self.donor, idempotency_key=first_key
        )
        self.assertEqual(key_conflict.status_code, status.HTTP_409_CONFLICT)

        complete = self.allocate(request_id, '3.00', user=self.donor)
        self.assertEqual(complete.status_code, status.HTTP_200_OK, complete.data)
        self.assertEqual(complete.data['status'], 'approved')
        self.assertEqual(Decimal(complete.data['remaining_quantity']), Decimal('0'))
        request_obj.refresh_from_db()
        self.assertEqual(request_obj.approved_quantity, Decimal('4.00'))

        allocations = self.client.get('/api/allocations/')
        self.assertEqual(allocations.status_code, status.HTTP_200_OK)
        self.assertEqual(allocations.data['count'], 2)
        self.assertEqual(
            self.client.post('/api/allocations/', {}, format='json').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_allocation_unit_conversion_and_request_cap(self):
        request_response = self.create_request(quantity='1.00', unit='kg')
        request_id = request_response.data['id']
        response = self.allocate(request_id, '1000.00', 'g', user=self.donor)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['status'], 'approved')

        second_request = self.create_request(
            user=self.recipient, quantity='1.00', unit='kg'
        )
        self.assertEqual(second_request.status_code, status.HTTP_201_CREATED, second_request.data)
        response = self.allocate(second_request.data['id'], '1.01', user=self.donor)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_total_allocations_cannot_exceed_donation_across_requests(self):
        first = self.create_request(quantity='5.00')
        second = self.create_request(
            user=self.other_recipient,
            organization=self.other_recipient_org,
            quantity='5.00',
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)

        first_allocation = self.allocate(first.data['id'], '3.00', user=self.donor)
        self.assertEqual(first_allocation.status_code, status.HTTP_200_OK)
        over = self.allocate(second.data['id'], '3.00', user=self.donor)
        self.assertEqual(over.status_code, status.HTTP_409_CONFLICT)
        allowed = self.allocate(second.data['id'], '2.00', user=self.donor)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK, allowed.data)
        self.donation.refresh_from_db()
        self.assertEqual(self.donation.status, 'reserved')
        self.assertEqual(DonationAllocation.objects.count(), 2)

    def test_only_donor_or_donor_organization_admin_can_allocate(self):
        response = self.create_request()
        request_id = response.data['id']
        forbidden = self.allocate(request_id, '1.00', user=self.recipient)
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        another = User.objects.create_user(username='donor-member', password='pass')
        Membership.objects.create(user=another, organization=self.donor_org, role='member')
        forbidden = self.allocate(request_id, '1.00', user=another)
        # Ordinary donor-org members cannot read or act on requests; keep those
        # records hidden instead of disclosing their existence.
        self.assertEqual(forbidden.status_code, status.HTTP_404_NOT_FOUND)

        donor_admin = User.objects.create_user(username='org-admin', password='pass')
        Membership.objects.create(user=donor_admin, organization=self.donor_org, role='admin')
        allowed = self.allocate(request_id, '1.00', user=donor_admin)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_reject_cancel_and_edit_status_transitions(self):
        rejected_request = self.create_request()
        self.client.force_authenticate(user=self.donor)
        rejected = self.client.post(
            f"/api/donation-requests/{rejected_request.data['id']}/reject/",
            {}, format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        self.assertEqual(rejected.data['status'], 'rejected')
        self.assertEqual(
            self.allocate(rejected_request.data['id'], '1.00', user=self.donor).status_code,
            status.HTTP_409_CONFLICT,
        )

        cancellable = self.create_request(
            user=self.other_recipient, organization=self.other_recipient_org
        )
        cancelled = self.client.post(
            f"/api/donation-requests/{cancellable.data['id']}/cancel/", {}, format='json'
        )
        self.assertEqual(cancelled.status_code, status.HTTP_200_OK)
        self.assertEqual(cancelled.data['status'], 'cancelled')

        editable = self.create_request(
            user=self.other_recipient, organization=self.other_recipient_org
        )
        self.client.force_authenticate(user=self.other_recipient)
        patched = self.client.patch(
            f"/api/donation-requests/{editable.data['id']}/",
            {'notes': 'Updated before review'}, format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK, patched.data)
        self.client.force_authenticate(user=self.donor)
        self.assertEqual(
            self.client.patch(
                f"/api/donation-requests/{editable.data['id']}/",
                {'notes': 'Donor cannot edit'}, format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_duplicate_open_request_and_delete_are_rejected(self):
        first = self.create_request()
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        duplicate = self.create_request()
        self.assertEqual(duplicate.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            self.client.delete(f"/api/donation-requests/{first.data['id']}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )


@skipUnless(
    connection.features.has_select_for_update,
    'Concurrent allocation test requires database row-lock support (for example PostgreSQL).',
)
class ConcurrentAllocationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        now = timezone.now()
        self.donor = User.objects.create_user(username='lock-donor', password='pass', role='donor')
        self.recipient = User.objects.create_user(
            username='lock-recipient', password='pass', role='recipient'
        )
        self.donor_org = Organization.objects.create(
            name='Lock donor org', org_type='restaurant', address='A', city='C', state='S',
            postal_code='1', phone='1', email='lock-donor@example.test', status='verified',
        )
        self.recipient_org = Organization.objects.create(
            name='Lock recipient org', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', phone='1', email='lock-recipient@example.test', status='verified',
        )
        Membership.objects.create(user=self.donor, organization=self.donor_org, role='owner')
        Membership.objects.create(user=self.recipient, organization=self.recipient_org, role='member')
        self.donation = Donation.objects.create(
            donor=self.donor, organization=self.donor_org, title='Concurrent food',
            description='Food', food_category='produce', quantity=Decimal('5.00'), unit='kg',
            available_from=now - timedelta(minutes=1),
            available_until=now + timedelta(days=1), pickup_address='A', status='published',
        )
        self.request_obj = DonationRequest.objects.create(
            recipient=self.recipient, organization=self.recipient_org, donation=self.donation,
            requested_quantity=Decimal('5.00'), requested_unit='kg', notes='',
        )

    def test_parallel_approvals_do_not_overallocate(self):
        def approve_three():
            client = APIClient()
            client.force_authenticate(user=self.donor)
            return client.post(
                f'/api/donation-requests/{self.request_obj.pk}/approve/',
                {'approved_quantity': '3.00', 'approved_unit': 'kg'},
                format='json',
                HTTP_IDEMPOTENCY_KEY=uuid4().hex,
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: approve_three(), range(2)))

        self.assertCountEqual(responses, [status.HTTP_200_OK, status.HTTP_409_CONFLICT])
        total = sum(
            (allocation.approved_quantity for allocation in DonationAllocation.objects.all()),
            Decimal('0'),
        )
        self.assertLessEqual(total, self.donation.quantity)
