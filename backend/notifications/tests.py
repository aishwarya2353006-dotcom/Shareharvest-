from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from donations.models import Donation
from donation_requests.models import DonationAllocation, DonationRequest
from notifications.models import Notification
from organizations.models import Membership, Organization
from pickups.models import Pickup


class NotificationApiAndEventsTests(APITestCase):
    def setUp(self):
        self.donor = User.objects.create_user('event-donor', password='test-pass', role='donor')
        self.donor_admin = User.objects.create_user('event-donor-admin', password='test-pass', role='donor')
        self.recipient = User.objects.create_user('event-recipient', password='test-pass', role='recipient')
        self.volunteer = User.objects.create_user('event-volunteer', password='test-pass', role='volunteer')
        self.stranger = User.objects.create_user('event-stranger', password='test-pass', role='recipient')
        self.donor_org = self.organization('Event donor org', 'restaurant')
        self.recipient_org = self.organization('Event recipient org', 'ngo')
        self.stranger_org = self.organization('Event stranger org', 'community')
        Membership.objects.create(user=self.donor, organization=self.donor_org, role='owner')
        Membership.objects.create(user=self.donor_admin, organization=self.donor_org, role='admin')
        Membership.objects.create(user=self.recipient, organization=self.recipient_org, role='member')
        Membership.objects.create(user=self.volunteer, organization=self.recipient_org, role='volunteer')
        Membership.objects.create(user=self.stranger, organization=self.stranger_org, role='member')
        now = timezone.now()
        self.donation = Donation.objects.create(
            donor=self.donor, organization=self.donor_org, title='Event vegetables',
            description='Test food', food_category='produce', quantity=Decimal('10'),
            unit='kg', available_from=now - timedelta(hours=1),
            available_until=now + timedelta(days=1), pickup_address='Test road', status='published',
        )

    def organization(self, name, org_type):
        return Organization.objects.create(
            name=name, org_type=org_type, address='Test road', city='City',
            state='State', postal_code='00000', country='USA', phone='555-0100',
            email=f'{name.lower().replace(" ", "-")}@example.test', status='verified',
        )

    def create_request(self, quantity='4.00'):
        return DonationRequest.objects.create(
            recipient=self.recipient, organization=self.recipient_org,
            donation=self.donation, requested_quantity=Decimal(quantity),
            requested_unit='kg', notes='Test request',
        )

    def test_request_submission_approval_and_rejection_notify_only_relevant_users(self):
        self.client.force_authenticate(self.recipient)
        response = self.client.post('/api/donation-requests/', {
            'donation': self.donation.pk, 'organization': self.recipient_org.pk,
            'requested_quantity': '4.00', 'requested_unit': 'kg', 'notes': 'Test request',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertSetEqual(
            set(Notification.objects.values_list('recipient_id', flat=True)),
            {self.donor.pk, self.donor_admin.pk},
        )
        from notifications.services import notify_request_submitted
        notify_request_submitted(DonationRequest.objects.get(pk=response.data['id']))
        self.assertEqual(Notification.objects.filter(notification_type='request_received').count(), 2)
        request_id = response.data['id']
        self.client.force_authenticate(self.donor)
        approved = self.client.post(
            f'/api/donation-requests/{request_id}/approve/',
            {'approved_quantity': '2.00', 'approved_unit': 'kg'}, format='json',
            HTTP_IDEMPOTENCY_KEY='event-approve-1',
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)
        self.assertEqual(Notification.objects.filter(recipient=self.recipient, notification_type='request_approved').count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.stranger).count(), 0)

        second_request = self.create_request_for_other_donation()
        rejected = self.client.post(f'/api/donation-requests/{second_request.pk}/reject/', {}, format='json')
        self.assertEqual(rejected.status_code, status.HTTP_200_OK, rejected.data)
        self.assertEqual(Notification.objects.filter(recipient=self.recipient, notification_type='request_rejected').count(), 1)

    def create_request_for_other_donation(self):
        donation = Donation.objects.create(
            donor=self.donor, organization=self.donor_org, title='Second food',
            description='Test food', food_category='produce', quantity=Decimal('10'),
            unit='kg', available_from=timezone.now() - timedelta(hours=1),
            available_until=timezone.now() + timedelta(days=1), pickup_address='Test road', status='published',
        )
        return self.create_request_for_donation(donation)

    def create_request_for_donation(self, donation):
        return DonationRequest.objects.create(
            recipient=self.recipient, organization=self.recipient_org, donation=donation,
            requested_quantity=Decimal('3'), requested_unit='kg',
        )

    def test_pickup_events_notify_parties_and_eligible_assigned_volunteer(self):
        request = self.create_request()
        request.status = 'approved'
        request.save(update_fields=['status', 'updated_at'])
        allocation = DonationAllocation.objects.create(
            request=request, approved_by=self.donor, approved_quantity=Decimal('4'),
            approved_unit='kg', idempotency_key=uuid4().hex,
        )
        pickup = Pickup.objects.create(
            donation=self.donation, request=request, allocation=allocation,
            pickup_type='volunteer', scheduled_at=timezone.now() + timedelta(hours=1),
            pickup_address='Test road', contact_person='Test', contact_phone='555-0100',
            volunteer=self.volunteer,
        )
        from notifications.services import notify_pickup
        notify_pickup(pickup, 'pickup_scheduled')
        self.assertSetEqual(
            set(Notification.objects.filter(related_object_type='pickup').values_list('recipient_id', flat=True)),
            {self.donor.pk, self.donor_admin.pk, self.recipient.pk, self.volunteer.pk},
        )
        count = Notification.objects.count()
        notify_pickup(pickup, 'pickup_scheduled')
        self.assertEqual(Notification.objects.count(), count)

    def test_pickup_create_api_notifies_authorized_parties(self):
        request = self.create_request()
        request.status = 'approved'
        request.save(update_fields=['status', 'updated_at'])
        allocation = DonationAllocation.objects.create(
            request=request, approved_by=self.donor, approved_quantity=Decimal('4'),
            approved_unit='kg', idempotency_key=uuid4().hex,
        )
        self.client.force_authenticate(self.donor)
        response = self.client.post('/api/pickups/', {
            'allocation': allocation.pk,
            'pickup_type': 'self',
            'scheduled_at': (timezone.now() + timedelta(hours=1)).isoformat(),
            'pickup_address': 'Test road',
            'contact_person': 'Test contact',
            'contact_phone': '555-0100',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            set(Notification.objects.filter(notification_type='pickup_scheduled').values_list('recipient_id', flat=True)),
            {self.donor.pk, self.donor_admin.pk, self.recipient.pk},
        )
        self.assertEqual(Notification.objects.filter(recipient=self.stranger).count(), 0)

    def test_notification_api_is_user_scoped_and_read_operations_are_owned(self):
        own = Notification.objects.create(
            recipient=self.recipient, notification_type='system', title='Own', message='Own message'
        )
        other = Notification.objects.create(
            recipient=self.stranger, notification_type='system', title='Other', message='Other message'
        )
        own_unread = Notification.objects.create(
            recipient=self.recipient, notification_type='system', title='Own unread', message='Another message'
        )
        self.client.force_authenticate(self.recipient)
        listing = self.client.get('/api/notifications/')
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual({entry['id'] for entry in listing.data['results']}, {own.pk, own_unread.pk})
        self.assertEqual(self.client.get('/api/notifications/unread-count/').data['count'], 2)
        self.assertEqual(self.client.post(f'/api/notifications/{other.pk}/read/').status_code, status.HTTP_404_NOT_FOUND)
        self.client.post(f'/api/notifications/{own.pk}/read/')
        own.refresh_from_db()
        self.assertTrue(own.is_read)
        self.assertIsNotNone(own.read_at)
        self.assertEqual(self.client.post('/api/notifications/mark-all-read/').data['updated'], 1)
        own_unread.refresh_from_db()
        self.assertTrue(own_unread.is_read)
        self.assertIsNotNone(own_unread.read_at)
        other.refresh_from_db()
        self.assertFalse(other.is_read)

    def test_pagination_and_newest_first_order(self):
        items = [Notification.objects.create(
            recipient=self.recipient, notification_type='system',
            title=f'Notice {index}', message='Message',
        ) for index in range(22)]
        self.client.force_authenticate(self.recipient)
        first_page = self.client.get('/api/notifications/')
        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(first_page.data['count'], 22)
        self.assertEqual(len(first_page.data['results']), 20)
        self.assertEqual(first_page.data['results'][0]['id'], items[-1].pk)
        self.assertIsNotNone(first_page.data['next'])
        second_page = self.client.get('/api/notifications/?page=2')
        self.assertEqual(len(second_page.data['results']), 2)

    def test_failed_request_validation_does_not_create_notification(self):
        self.client.force_authenticate(self.recipient)
        response = self.client.post('/api/donation-requests/', {
            'donation': self.donation.pk, 'organization': self.recipient_org.pk,
            'requested_quantity': '0', 'requested_unit': 'kg', 'notes': 'Invalid',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Notification.objects.count(), 0)

    def test_pickup_lifecycle_actions_create_notifications(self):
        request = self.create_request()
        request.status = 'approved'
        request.save(update_fields=['status', 'updated_at'])
        allocation = DonationAllocation.objects.create(
            request=request, approved_by=self.donor, approved_quantity=Decimal('4'),
            approved_unit='kg', idempotency_key=uuid4().hex,
        )
        self.client.force_authenticate(self.donor)
        response = self.client.post('/api/pickups/', {
            'allocation': allocation.pk,
            'pickup_type': 'self',
            'scheduled_at': (timezone.now() + timedelta(hours=1)).isoformat(),
            'pickup_address': 'Test road',
            'contact_person': 'Test contact',
            'contact_phone': '555-0100',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        pickup_id = response.data['id']
        # Move scheduled time to the past so it can be started
        from pickups.models import Pickup
        pickup = Pickup.objects.get(pk=pickup_id)
        pickup.scheduled_at = timezone.now() - timedelta(minutes=1)
        pickup.save(update_fields=['scheduled_at'])
        # Clear notifications from creation to test lifecycle actions
        Notification.objects.all().delete()
        # Start pickup
        start_response = self.client.post(f'/api/pickups/{pickup_id}/start/')
        self.assertEqual(start_response.status_code, status.HTTP_200_OK, start_response.data)
        self.assertTrue(
            Notification.objects.filter(notification_type='pickup_started').exists()
        )
        # Complete pickup
        complete_response = self.client.post(
            f'/api/pickups/{pickup_id}/complete/',
            {'actual_quantity': '4.00', 'actual_unit': 'kg'}, format='json',
        )
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK, complete_response.data)
        self.assertTrue(
            Notification.objects.filter(notification_type='pickup_completed').exists()
        )
        # Verify stranger not notified
        self.assertEqual(Notification.objects.filter(recipient=self.stranger).count(), 0)

    def test_notification_api_requires_authentication(self):
        response = self.client.get('/api/notifications/')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_pickup_cancelled_notifies_authorized_parties_and_excludes_stranger(self):
        request = self.create_request()
        request.status = 'approved'
        request.save(update_fields=['status', 'updated_at'])
        allocation = DonationAllocation.objects.create(
            request=request, approved_by=self.donor, approved_quantity=Decimal('4'),
            approved_unit='kg', idempotency_key=uuid4().hex,
        )
        pickup = Pickup.objects.create(
            donation=self.donation, request=request, allocation=allocation,
            pickup_type='self', scheduled_at=timezone.now() + timedelta(hours=2),
            pickup_address='Test road', contact_person='Test', contact_phone='555-0100',
        )
        self.client.force_authenticate(self.donor)
        response = self.client.post(f'/api/pickups/{pickup.pk}/cancel/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            set(Notification.objects.filter(notification_type='pickup_cancelled').values_list('recipient_id', flat=True)),
            {self.donor.pk, self.donor_admin.pk, self.recipient.pk},
        )
        self.assertEqual(Notification.objects.filter(recipient=self.stranger).count(), 0)
        # Deduplication: re-delivering the same event key must not duplicate.
        before = Notification.objects.count()
        from notifications.services import notify_pickup
        notify_pickup(pickup, 'pickup_cancelled')
        self.assertEqual(Notification.objects.count(), before)
        # A stranger outside the organizations cannot cancel.
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.post(f'/api/pickups/{pickup.pk}/cancel/').status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_pickup_no_show_notifies_authorized_parties_and_excludes_stranger(self):
        request = self.create_request()
        request.status = 'approved'
        request.save(update_fields=['status', 'updated_at'])
        allocation = DonationAllocation.objects.create(
            request=request, approved_by=self.donor, approved_quantity=Decimal('4'),
            approved_unit='kg', idempotency_key=uuid4().hex,
        )
        pickup = Pickup.objects.create(
            donation=self.donation, request=request, allocation=allocation,
            pickup_type='self', scheduled_at=timezone.now() - timedelta(minutes=5),
            pickup_address='Test road', contact_person='Test', contact_phone='555-0100',
        )
        self.client.force_authenticate(self.donor)
        response = self.client.post(f'/api/pickups/{pickup.pk}/no-show/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(
            Notification.objects.filter(notification_type='pickup_no_show').exists()
        )
        self.assertEqual(
            set(Notification.objects.filter(notification_type='pickup_no_show').values_list('recipient_id', flat=True)),
            {self.donor.pk, self.donor_admin.pk, self.recipient.pk},
        )
        self.assertEqual(Notification.objects.filter(recipient=self.stranger).count(), 0)
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.post(f'/api/pickups/{pickup.pk}/no-show/').status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_pickup_failed_notifies_authorized_parties_and_excludes_stranger(self):
        request = self.create_request()
        request.status = 'approved'
        request.save(update_fields=['status', 'updated_at'])
        allocation = DonationAllocation.objects.create(
            request=request, approved_by=self.donor, approved_quantity=Decimal('4'),
            approved_unit='kg', idempotency_key=uuid4().hex,
        )
        pickup = Pickup.objects.create(
            donation=self.donation, request=request, allocation=allocation,
            pickup_type='self', scheduled_at=timezone.now() - timedelta(minutes=5),
            pickup_address='Test road', contact_person='Test', contact_phone='555-0100',
        )
        self.client.force_authenticate(self.donor)
        start_response = self.client.post(f'/api/pickups/{pickup.pk}/start/')
        self.assertEqual(start_response.status_code, status.HTTP_200_OK, start_response.data)
        fail_response = self.client.post(
            f'/api/pickups/{pickup.pk}/fail/',
            {'failure_reason': 'Vehicle broke down.'}, format='json',
        )
        self.assertEqual(fail_response.status_code, status.HTTP_200_OK, fail_response.data)
        self.assertTrue(
            Notification.objects.filter(notification_type='pickup_failed').exists()
        )
        self.assertEqual(
            set(Notification.objects.filter(notification_type='pickup_failed').values_list('recipient_id', flat=True)),
            {self.donor.pk, self.donor_admin.pk, self.recipient.pk},
        )
        self.assertEqual(Notification.objects.filter(recipient=self.stranger).count(), 0)
        self.client.force_authenticate(self.stranger)
        self.assertEqual(
            self.client.post(f'/api/pickups/{pickup.pk}/fail/', {'failure_reason': 'x'}, format='json').status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_pickup_volunteer_assigned_notifies_eligible_volunteer_and_is_isolated(self):
        request = self.create_request()
        request.status = 'approved'
        request.save(update_fields=['status', 'updated_at'])
        allocation = DonationAllocation.objects.create(
            request=request, approved_by=self.donor, approved_quantity=Decimal('4'),
            approved_unit='kg', idempotency_key=uuid4().hex,
        )
        pickup = Pickup.objects.create(
            donation=self.donation, request=request, allocation=allocation,
            pickup_type='volunteer', scheduled_at=timezone.now() + timedelta(hours=2),
            pickup_address='Test road', contact_person='Test', contact_phone='555-0100',
        )
        self.client.force_authenticate(self.donor)
        response = self.client.post(
            f'/api/pickups/{pickup.pk}/assign-volunteer/',
            {'volunteer': self.volunteer.pk}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.volunteer, notification_type='pickup_volunteer_assigned'
            ).exists()
        )
        self.assertEqual(Notification.objects.filter(recipient=self.stranger).count(), 0)
        # A volunteer from an unrelated organization cannot be assigned.
        self.client.force_authenticate(self.donor)
        bad_response = self.client.post(
            f'/api/pickups/{pickup.pk}/assign-volunteer/',
            {'volunteer': self.stranger.pk}, format='json',
        )
        self.assertEqual(bad_response.status_code, status.HTTP_400_BAD_REQUEST, bad_response.data)
