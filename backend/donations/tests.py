from django.test import TestCase, Client
from donations.models import Donation
from donation_requests.models import DonationAllocation, DonationRequest
from organizations.models import Organization, Membership
from accounts.models import User
from rest_framework import status
import json
from django.utils import timezone
import datetime
from unittest.mock import patch

class DonationViewSetTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
        self.org = Organization.objects.create(
            name='Test Org',
            org_type='restaurant',
            address='123 Main St',
            city='City',
            state='State',
            postal_code='12345',
            country='USA',
            phone='123-456-7890',
            email='test@example.com',
            status='verified'  # Make sure the organization is verified for publishing
        )
        # Create a membership for user1 in the organization
        Membership.objects.create(user=self.user1, organization=self.org, role='owner', is_active=True)
        # No membership for user2 in the organization

    def test_donation_creation_by_member(self):
        # User1 creates a donation
        self.client.force_login(self.user1)
        response = self.client.post(
            '/api/donations/donations/',
            data=json.dumps({
                'title': 'Test Donation',
                'description': 'A test donation',
                'food_category': 'prepared',
                'quantity': 10.0,
                'unit': 'kg',
                'available_from': '2026-10-15T10:00:00Z',
                'available_until': '2026-10-16T10:00:00Z',
                'pickup_address': '123 Pickup St',
                'organization': self.org.id
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Donation.objects.count(), 1)
        donation = Donation.objects.first()
        self.assertEqual(donation.title, 'Test Donation')
        self.assertEqual(donation.donor, self.user1)
        self.assertEqual(donation.organization, self.org)
        self.assertEqual(donation.status, 'draft')  # Default status

    def test_donation_creation_by_non_member(self):
        # User2 tries to create a donation for the organization (not a member)
        self.client.force_login(self.user2)
        response = self.client.post(
            '/api/donations/donations/',
            data=json.dumps({
                'title': 'Test Donation',
                'description': 'A test donation',
                'food_category': 'prepared',
                'quantity': 10.0,
                'unit': 'kg',
                'available_from': '2026-10-15T10:00:00Z',
                'available_until': '2026-10-16T10:00:00Z',
                'pickup_address': '123 Pickup St',
                'organization': self.org.id
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_recipient_member_cannot_create_donation(self):
        recipient = User.objects.create_user(username='recipient-donor-check', password='pass', role='recipient')
        Membership.objects.create(user=recipient, organization=self.org, role='owner', is_active=True)
        self.client.force_login(recipient)
        response = self.client.post(
            '/api/donations/donations/',
            data=json.dumps({
                'title': 'Not a donor listing', 'description': 'Food',
                'food_category': 'produce', 'quantity': 2, 'unit': 'kg',
                'available_from': '2026-10-15T10:00:00Z',
                'available_until': '2026-10-16T10:00:00Z',
                'pickup_address': '123 Main St', 'organization': self.org.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_donation_creation_invalid_quantity(self):
        self.client.force_login(self.user1)
        response = self.client.post(
            '/api/donations/donations/',
            data=json.dumps({
                'title': 'Test Donation',
                'description': 'A test donation',
                'food_category': 'prepared',
                'quantity': -5.0,  # Invalid
                'unit': 'kg',
                'available_from': '2026-10-15T10:00:00Z',
                'available_until': '2026-10-16T10:00:00Z',
                'pickup_address': '123 Pickup St',
                'organization': self.org.id
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', response.json())

    def test_donation_creation_invalid_dates(self):
        self.client.force_login(self.user1)
        response = self.client.post(
            '/api/donations/donations/',
            data=json.dumps({
                'title': 'Test Donation',
                'description': 'A test donation',
                'food_category': 'prepared',
                'quantity': 10.0,
                'unit': 'kg',
                'available_from': '2026-10-16T10:00:00Z',  # After available_until
                'available_until': '2026-10-15T10:00:00Z',
                'pickup_address': '123 Pickup St',
                'organization': self.org.id
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('available_until', response.json())

    def test_donation_edits_cannot_invalidate_allocations_or_request_units(self):
        now = timezone.now()
        donation = Donation.objects.create(
            donor=self.user1, organization=self.org, title='Allocated food',
            description='Food', food_category='produce', quantity=5, unit='kg',
            available_from=now - datetime.timedelta(hours=1),
            available_until=now + datetime.timedelta(days=1),
            pickup_address='Pickup', status='published',
        )
        recipient = User.objects.create_user(username='allocation-recipient', password='pass', role='recipient')
        recipient_org = Organization.objects.create(
            name='Allocation recipient', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', country='USA', phone='1', email='allocation-recipient@example.test',
            status='verified',
        )
        request_obj = DonationRequest.objects.create(
            recipient=recipient, organization=recipient_org, donation=donation,
            requested_quantity=3, requested_unit='kg',
        )
        DonationAllocation.objects.create(
            request=request_obj, approved_by=self.user1,
            approved_quantity=2, approved_unit='kg', idempotency_key='allocated-edit-test',
        )

        self.client.force_login(self.user1)
        reduce_below_allocated = self.client.patch(
            f'/api/donations/donations/{donation.id}/',
            data=json.dumps({'quantity': 1}), content_type='application/json',
        )
        self.assertEqual(reduce_below_allocated.status_code, status.HTTP_400_BAD_REQUEST)
        change_incompatible_unit = self.client.patch(
            f'/api/donations/donations/{donation.id}/',
            data=json.dumps({'unit': 'l'}), content_type='application/json',
        )
        self.assertEqual(change_incompatible_unit.status_code, status.HTTP_400_BAD_REQUEST)

    def test_donation_publishing_requirement(self):
        # Create a donation in draft status by user1
        self.client.force_login(self.user1)
        response = self.client.post(
            '/api/donations/donations/',
            data=json.dumps({
                'title': 'Test Donation',
                'description': 'A test donation',
                'food_category': 'prepared',
                'quantity': 10.0,
                'unit': 'kg',
                'available_from': '2026-10-15T10:00:00Z',
                'available_until': '2026-10-16T10:00:00Z',
                'pickup_address': '123 Pickup St',
                'organization': self.org.id
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        donation_id = response.json()['id']

        # Try to publish the donation by user1 (who is an owner) -> should succeed because organization is verified
        self.client.force_login(self.user1)
        response = self.client.patch(
            f'/api/donations/donations/{donation_id}/',
            data=json.dumps({'status': 'published'}),
            content_type='application/json'
        )
        print(f'First publish response status: {response.status_code}')
        print(f'First publish response data: {response.json()}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'published')
        self.assertIsNotNone(response.json()['published_at'])

        # Now, create an unverified organization
        org_unverified = Organization.objects.create(
            name='Unverified Org',
            org_type='restaurant',
            address='456 Oak Ave',
            city='City',
            state='State',
            postal_code='12345',
            country='USA',
            phone='098-765-4321',
            email='test2@example.com',
            status='pending'  # Not verified
        )
        # Create a membership for user1 in the unverified organization
        Membership.objects.create(user=self.user1, organization=org_unverified, role='owner', is_active=True)
        # Create a donation for the unverified organization
        response = self.client.post(
            '/api/donations/donations/',
            data=json.dumps({
                'title': 'Unverified Donation',
                'description': 'A donation from an unverified org',
                'food_category': 'prepared',
                'quantity': 5.0,
                'unit': 'kg',
                'available_from': '2026-10-15T10:00:00Z',
                'available_until': '2026-10-16T10:00:00Z',
                'pickup_address': '456 Pickup St',
                'organization': org_unverified.id
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        unverified_donation_id = response.json()['id']

        # Try to publish the donation from the unverified organization -> should fail
        self.client.force_login(self.user1)
        response = self.client.patch(
            f'/api/donations/donations/{unverified_donation_id}/',
            data=json.dumps({'status': 'published'}),
            content_type='application/json'
        )
        print(f'Second publish response status: {response.status_code}')
        print(f'Second publish response data: {response.json()}')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Only verified organizations can publish donations.', str(response.json()))

    def test_donation_listing_isolation(self):
        # Create two organizations: one for user1 and one for user2
        org1 = Organization.objects.create(
            name='Org1',
            org_type='restaurant',
            address='123 Main St',
            city='City',
            state='State',
            postal_code='12345',
            country='USA',
            phone='123-456-7890',
            email='test1@example.com',
            status='verified'
        )
        org2 = Organization.objects.create(
            name='Org2',
            org_type='hotel',
            address='456 Oak Ave',
            city='City',
            state='State',
            postal_code='12345',
            country='USA',
            phone='098-765-4321',
            email='test2@example.com',
            status='verified'
        )
        # Create memberships
        Membership.objects.create(user=self.user1, organization=org1, role='owner', is_active=True)
        Membership.objects.create(user=self.user2, organization=org2, role='owner', is_active=True)

        # Create a donation in each organization
        donation1 = Donation.objects.create(
            title='Donation 1',
            description='Description 1',
            food_category='prepared',
            quantity=10.0,
            unit='kg',
            available_from='2026-10-15T10:00:00Z',
            available_until='2026-10-16T10:00:00Z',
            pickup_address='123 Pickup St',
            donor=self.user1,
            organization=org1,
            status='published'
        )
        donation2 = Donation.objects.create(
            title='Donation 2',
            description='Description 2',
            food_category='prepared',
            quantity=5.0,
            unit='kg',
            available_from='2026-10-15T10:00:00Z',
            available_until='2026-10-16T10:00:00Z',
            pickup_address='456 Pickup St',
            donor=self.user2,
            organization=org2,
            status='published'
        )

        # User1 should see only donation1
        self.client.force_login(self.user1)
        response = self.client.get('/api/donations/donations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['title'], 'Donation 1')

        # User2 should see only donation2
        self.client.force_login(self.user2)
        response = self.client.get('/api/donations/donations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['title'], 'Donation 2')

    def test_donation_expiry_filtering(self):
        # Create a donation that will expire in the past
        expired_donation = Donation.objects.create(
            title='Expired Donation',
            description='An expired donation',
            food_category='prepared',
            quantity=5.0,
            unit='kg',
            available_from=timezone.now() - datetime.timedelta(days=2),
            available_until=timezone.now() - datetime.timedelta(days=1),
            pickup_address='123 Expired St',
            donor=self.user1,
            organization=self.org,
            status='published'
        )
        # Create a donation that is still valid (future)
        valid_donation = Donation.objects.create(
            title='Valid Donation',
            description='A valid donation',
            food_category='prepared',
            quantity=5.0,
            unit='kg',
            available_from=timezone.now() + datetime.timedelta(days=1),
            available_until=timezone.now() + datetime.timedelta(days=2),
            pickup_address='123 Valid St',
            donor=self.user1,
            organization=self.org,
            status='published'
        )
        # Manually set the expired donation's status to 'expired' to simulate the expiry command having run
        expired_donation.status = 'expired'
        expired_donation.save()

        # Test that a regular user (user1) does not see the expired donation
        self.client.force_login(self.user1)
        response = self.client.get('/api/donations/donations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)  # Only the valid donation should be returned
        self.assertEqual(data['results'][0]['title'], 'Valid Donation')

        # Test that an admin user can see both donations
        admin_user = User.objects.create_user(username='admin', password='pass', role='admin')
        self.client.force_login(admin_user)
        response = self.client.get('/api/donations/donations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 2)  # Admin sees both expired and valid
        titles = {donation['title'] for donation in data['results']}
        self.assertEqual(titles, {'Expired Donation', 'Valid Donation'})

    def test_donor_mine_filter_includes_own_expired_and_excludes_other_donors(self):
        Membership.objects.create(user=self.user2, organization=self.org, role='member')
        own_expired = Donation.objects.create(
            title='My expired donation', description='Expired', food_category='produce',
            quantity=2, unit='kg', available_from=timezone.now() - datetime.timedelta(days=2),
            available_until=timezone.now() - datetime.timedelta(days=1),
            pickup_address='My address', donor=self.user1, organization=self.org, status='expired',
        )
        Donation.objects.create(
            title='Other donor donation', description='Other donor', food_category='produce',
            quantity=3, unit='kg', available_from=timezone.now(),
            available_until=timezone.now() + datetime.timedelta(days=1),
            pickup_address='Other address', donor=self.user2, organization=self.org, status='published',
        )

        self.client.force_login(self.user1)
        response = self.client.get('/api/donations/donations/?mine=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['count'], 1)
        self.assertEqual(response.json()['results'][0]['id'], own_expired.id)

    def test_donor_mine_filter_returns_empty_list_for_new_donor(self):
        self.client.force_login(self.user2)
        response = self.client.get('/api/donations/donations/?mine=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['count'], 0)
        self.assertEqual(response.json()['results'], [])

    def test_recipient_browse_returns_only_current_published_offers(self):
        now = timezone.now()
        base = {
            'description': 'Food', 'food_category': 'produce', 'quantity': 2,
            'unit': 'kg', 'pickup_address': 'Address', 'donor': self.user1,
            'organization': self.org,
        }
        eligible = Donation.objects.create(
            **base, title='Available', status='published',
            available_from=now - datetime.timedelta(minutes=1),
            available_until=now + datetime.timedelta(hours=1),
        )
        exhausted = Donation.objects.create(
            **{**base, 'quantity': 1}, title='Exhausted', status='published',
            available_from=now - datetime.timedelta(minutes=1),
            available_until=now + datetime.timedelta(hours=1),
        )
        for title, donation_status, start, end in (
            ('Draft', 'draft', now - datetime.timedelta(minutes=1), now + datetime.timedelta(hours=1)),
            ('Expired', 'published', now - datetime.timedelta(hours=2), now - datetime.timedelta(hours=1)),
            ('Future', 'published', now + datetime.timedelta(hours=1), now + datetime.timedelta(hours=2)),
            ('Reserved', 'reserved', now - datetime.timedelta(minutes=1), now + datetime.timedelta(hours=1)),
        ):
            Donation.objects.create(
                **base, title=title, status=donation_status,
                available_from=start, available_until=end,
            )

        recipient = User.objects.create_user(username='browse-recipient', password='pass', role='recipient')
        recipient_org = Organization.objects.create(
            name='Browse recipient org', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', country='USA', phone='1', email='browse-recipient@example.test',
            status='verified',
        )
        request_obj = DonationRequest.objects.create(
            recipient=recipient, organization=recipient_org, donation=exhausted,
            requested_quantity=1, requested_unit='kg',
        )
        DonationAllocation.objects.create(
            request=request_obj, approved_by=self.user1, approved_quantity=1,
            approved_unit='kg', idempotency_key='exhausted-stock',
        )
        self.client.force_login(recipient)
        response = self.client.get('/api/donations/donations/?browse=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in response.json()['results']], [eligible.id])

        self.client.force_login(self.user1)
        forbidden = self.client.get('/api/donations/donations/?browse=true')
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_scheduled_published_offer_appears_only_during_its_availability_window(self):
        now = timezone.now()
        scheduled = Donation.objects.create(
            title='Scheduled vegetables', description='Food', food_category='produce',
            quantity=5, unit='kg', pickup_address='Address', donor=self.user1,
            organization=self.org, status='published',
            available_from=now + datetime.timedelta(hours=1),
            available_until=now + datetime.timedelta(hours=2),
        )
        unpublished = Donation.objects.create(
            title='Unpublished vegetables', description='Food', food_category='produce',
            quantity=5, unit='kg', pickup_address='Address', donor=self.user1,
            organization=self.org, status='draft',
            available_from=now - datetime.timedelta(hours=1),
            available_until=now + datetime.timedelta(hours=2),
        )
        expired = Donation.objects.create(
            title='Expired vegetables', description='Food', food_category='produce',
            quantity=5, unit='kg', pickup_address='Address', donor=self.user1,
            organization=self.org, status='published',
            available_from=now - datetime.timedelta(hours=2),
            available_until=now - datetime.timedelta(hours=1),
        )
        recipient = User.objects.create_user(
            username='scheduled-browse-recipient', password='pass', role='recipient'
        )
        self.client.force_login(recipient)

        with patch('donations.views.timezone.now', return_value=now):
            before_window = self.client.get('/api/donations/donations/?browse=true')
        self.assertEqual(before_window.status_code, status.HTTP_200_OK)
        self.assertEqual(before_window.json()['results'], [])

        with patch('donations.views.timezone.now', return_value=now + datetime.timedelta(hours=1, minutes=30)):
            during_window = self.client.get('/api/donations/donations/?browse=true')
        self.assertEqual(during_window.status_code, status.HTTP_200_OK)
        visible_ids = [item['id'] for item in during_window.json()['results']]
        self.assertEqual(visible_ids, [scheduled.id])
        self.assertNotIn(unpublished.id, visible_ids)
        self.assertNotIn(expired.id, visible_ids)

        with patch('donations.views.timezone.now', return_value=now + datetime.timedelta(hours=3)):
            after_window = self.client.get('/api/donations/donations/?browse=true')
        self.assertEqual(after_window.status_code, status.HTTP_200_OK)
        self.assertEqual(after_window.json()['results'], [])
