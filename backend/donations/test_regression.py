from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from donations.models import Donation
from organizations.models import Organization, Membership
from accounts.models import User
from rest_framework import status
import json

class DonationStatusTransitionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='admin_st', password='pass', role='admin')
        self.donor = User.objects.create_user(username='donor_st', password='pass', role='donor')
        self.org = Organization.objects.create(
            name='Org ST', org_type='restaurant', address='1 St', city='City',
            state='State', postal_code='12345', country='USA', phone='111',
            email='st@example.com', status='verified'
        )
        Membership.objects.create(user=self.donor, organization=self.org, role='owner', is_active=True)

    def _create_donation(self, status_val):
        return Donation.objects.create(
            donor=self.donor, organization=self.org, title='Test Donation',
            description='Desc', food_category='prepared', quantity=10, unit='kg',
            available_from=timezone.now(), available_until=timezone.now() + timedelta(days=1),
            pickup_address='123 St', status=status_val
        )

    def test_admin_cannot_reopen_completed_donation(self):
        donation = self._create_donation('completed')
        self.client.force_login(self.admin)
        response = self.client.patch(
            f'/api/donations/donations/{donation.id}/',
            data=json.dumps({'status': 'published'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        donation.refresh_from_db()
        self.assertEqual(donation.status, 'completed')

    def test_admin_cannot_reopen_cancelled_donation(self):
        donation = self._create_donation('cancelled')
        self.client.force_login(self.admin)
        response = self.client.patch(
            f'/api/donations/donations/{donation.id}/',
            data=json.dumps({'status': 'published'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        donation.refresh_from_db()
        self.assertEqual(donation.status, 'cancelled')

    def test_admin_cannot_reopen_expired_donation(self):
        donation = self._create_donation('expired')
        self.client.force_login(self.admin)
        response = self.client.patch(
            f'/api/donations/donations/{donation.id}/',
            data=json.dumps({'status': 'published'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        donation.refresh_from_db()
        self.assertEqual(donation.status, 'expired')

    def test_valid_transition_draft_to_published(self):
        donation = self._create_donation('draft')
        self.client.force_login(self.donor)
        response = self.client.patch(
            f'/api/donations/donations/{donation.id}/',
            data=json.dumps({'status': 'published'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        donation.refresh_from_db()
        self.assertEqual(donation.status, 'published')

    def test_invalid_transition_for_ordinary_user(self):
        donation = self._create_donation('completed')
        self.client.force_login(self.donor)
        response = self.client.patch(
            f'/api/donations/donations/{donation.id}/',
            data=json.dumps({'status': 'published'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PickupPrivacyTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.donor = User.objects.create_user(username='donor_pp', password='pass', role='donor')
        self.recipient = User.objects.create_user(username='recipient_pp', password='pass', role='recipient')
        self.org = Organization.objects.create(
            name='Org PP', org_type='restaurant', address='1 St', city='City',
            state='State', postal_code='12345', country='USA', phone='111',
            email='pp@example.com', status='verified'
        )
        Membership.objects.create(user=self.donor, organization=self.org, role='owner', is_active=True)
        self.donation = Donation.objects.create(
            donor=self.donor, organization=self.org, title='Donation PP',
            description='Desc', food_category='prepared', quantity=10, unit='kg',
            available_from=timezone.now() - timedelta(hours=1),
            available_until=timezone.now() + timedelta(days=1),
            pickup_address='123 Secret St', pickup_instructions='Ring bell',
            status='published'
        )

    def test_browse_excludes_pickup_address_and_instructions(self):
        self.client.force_login(self.recipient)
        response = self.client.get('/api/donations/donations/?browse=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data if isinstance(data, list) else data.get('results', [])
        self.assertTrue(len(results) > 0)
        for item in results:
            self.assertNotIn('pickup_address', item)
            self.assertNotIn('pickup_instructions', item)
            # Non-sensitive fields remain
            self.assertIn('title', item)
            self.assertIn('quantity', item)

    def test_authorised_user_can_access_pickup_details(self):
        self.client.force_login(self.donor)
        response = self.client.get(f'/api/donations/donations/{self.donation.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('pickup_address', data)
        self.assertEqual(data['pickup_address'], '123 Secret St')
