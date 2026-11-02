from django.test import TestCase, Client
from django.utils import timezone
from donations.models import Donation
from donation_requests.models import DonationRequest
from organizations.models import Organization, Membership
from accounts.models import User
from rest_framework import status
import datetime

class CrossOrgIsolationTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Org A
        self.user_a = User.objects.create_user(username='user_a', password='pass', role='donor')
        self.org_a = Organization.objects.create(
            name='Org A', org_type='restaurant', address='1 A St', city='City',
            state='State', postal_code='12345', country='USA', phone='111',
            email='a@example.com', status='verified'
        )
        Membership.objects.create(user=self.user_a, organization=self.org_a, role='owner', is_active=True)
        # Org B
        self.user_b = User.objects.create_user(username='user_b', password='pass', role='donor')
        self.org_b = Organization.objects.create(
            name='Org B', org_type='hotel', address='2 B St', city='City',
            state='State', postal_code='12345', country='USA', phone='222',
            email='b@example.com', status='verified'
        )
        Membership.objects.create(user=self.user_b, organization=self.org_b, role='owner', is_active=True)
        # Recipient in Org B
        self.recipient_b = User.objects.create_user(username='recipient_b', password='pass', role='recipient')
        Membership.objects.create(user=self.recipient_b, organization=self.org_b, role='member', is_active=True)
        # Donation in Org A
        self.donation_a = Donation.objects.create(
            donor=self.user_a, organization=self.org_a, title='Donation A',
            description='Desc', food_category='prepared', quantity=10, unit='kg',
            available_from=timezone.now() - datetime.timedelta(hours=1),
            available_until=timezone.now() + datetime.timedelta(days=1),
            pickup_address='123 A St', status='published'
        )
        # DonationRequest in Org A (recipient_b is not in Org A, so use user_a's org)
        # Actually create a request from Org B recipient to Org A donation? No - test isolation.
        # Create request in Org A by a recipient in Org A
        self.recipient_a = User.objects.create_user(username='recipient_a', password='pass', role='recipient')
        Membership.objects.create(user=self.recipient_a, organization=self.org_a, role='member', is_active=True)
        self.request_a = DonationRequest.objects.create(
            donation=self.donation_a, organization=self.org_a, recipient=self.recipient_a,
            requested_quantity=5, requested_unit='kg', status='pending'
        )

    def test_org_b_cannot_list_org_a_donations(self):
        self.client.force_login(self.user_b)
        response = self.client.get('/api/donations/donations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Org B should not see Org A's donation
        ids = [d['id'] for d in data.get('results', data if isinstance(data, list) else [])]
        self.assertNotIn(self.donation_a.id, ids)

    def test_org_b_cannot_retrieve_org_a_donation(self):
        self.client.force_login(self.user_b)
        response = self.client.get(f'/api/donations/donations/{self.donation_a.id}/')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_org_b_cannot_list_org_a_donation_requests(self):
        self.client.force_login(self.user_b)
        response = self.client.get('/api/donation-requests/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get('results', data if isinstance(data, list) else [])
        ids = [r['id'] for r in results]
        self.assertNotIn(self.request_a.id, ids)

    def test_org_b_cannot_retrieve_org_a_donation_request(self):
        self.client.force_login(self.user_b)
        response = self.client.get(f'/api/donation-requests/{self.request_a.id}/')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_unauthenticated_cannot_access_donations(self):
        response = self.client.get('/api/donations/donations/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_unauthenticated_cannot_access_donation_requests(self):
        response = self.client.get('/api/donation-requests/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_org_a_can_access_own_donation(self):
        self.client.force_login(self.user_a)
        response = self.client.get(f'/api/donations/donations/{self.donation_a.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_org_a_can_access_own_donation_request(self):
        self.client.force_login(self.recipient_a)
        response = self.client.get(f'/api/donation-requests/{self.request_a.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
