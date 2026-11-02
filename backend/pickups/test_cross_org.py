from django.test import TestCase, Client
from django.utils import timezone
from donations.models import Donation
from donation_requests.models import DonationRequest, DonationAllocation
from pickups.models import Pickup
from organizations.models import Organization, Membership
from accounts.models import User
from rest_framework import status
import datetime

class CrossOrgPickupIsolationTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Org A
        self.user_a = User.objects.create_user(username='user_pa', password='pass', role='donor')
        self.org_a = Organization.objects.create(
            name='Org PA', org_type='restaurant', address='1 A St', city='City',
            state='State', postal_code='12345', country='USA', phone='111',
            email='pa@example.com', status='verified'
        )
        Membership.objects.create(user=self.user_a, organization=self.org_a, role='owner', is_active=True)
        # Org B
        self.user_b = User.objects.create_user(username='user_pb', password='pass', role='donor')
        self.org_b = Organization.objects.create(
            name='Org PB', org_type='hotel', address='2 B St', city='City',
            state='State', postal_code='12345', country='USA', phone='222',
            email='pb@example.com', status='verified'
        )
        Membership.objects.create(user=self.user_b, organization=self.org_b, role='owner', is_active=True)
        # Recipient in Org A
        self.recipient_a = User.objects.create_user(username='recipient_pa', password='pass', role='recipient')
        Membership.objects.create(user=self.recipient_a, organization=self.org_a, role='member', is_active=True)
        # Donation in Org A
        self.donation_a = Donation.objects.create(
            donor=self.user_a, organization=self.org_a, title='Donation PA',
            description='Desc', food_category='prepared', quantity=10, unit='kg',
            available_from=timezone.now() - datetime.timedelta(hours=1),
            available_until=timezone.now() + datetime.timedelta(days=1),
            pickup_address='123 A St', status='published'
        )
        # Request in Org A
        self.request_a = DonationRequest.objects.create(
            donation=self.donation_a, organization=self.org_a, recipient=self.recipient_a,
            requested_quantity=5, requested_unit='kg', status='approved'
        )
        # Allocation
        self.allocation_a = DonationAllocation.objects.create(
            request=self.request_a, approved_by=self.user_a,
            approved_quantity=5, approved_unit='kg', notes=''
        )
        # Pickup
        self.pickup_a = Pickup.objects.create(
            donation=self.donation_a, request=self.request_a, allocation=self.allocation_a,
            pickup_type='self', scheduled_at=timezone.now() + datetime.timedelta(days=1),
            pickup_address='123 A St', contact_person='Contact', contact_phone='111'
        )

    def test_org_b_cannot_list_org_a_pickups(self):
        self.client.force_login(self.user_b)
        response = self.client.get('/api/pickups/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        results = data.get('results', data if isinstance(data, list) else [])
        ids = [p['id'] for p in results]
        self.assertNotIn(self.pickup_a.id, ids)

    def test_org_b_cannot_retrieve_org_a_pickup(self):
        self.client.force_login(self.user_b)
        response = self.client.get(f'/api/pickups/{self.pickup_a.id}/')
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_unauthenticated_cannot_access_pickups(self):
        response = self.client.get('/api/pickups/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_org_a_can_access_own_pickup(self):
        self.client.force_login(self.user_a)
        response = self.client.get(f'/api/pickups/{self.pickup_a.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
