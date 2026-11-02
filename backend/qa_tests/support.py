from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase, APIClient

from accounts.models import User
from donations.models import Donation
from organizations.models import Membership, Organization


class DonationWorkflowTestCase(APITestCase):
    def setUp(self):
        self.donor = User.objects.create_user(
            username='qa-donor', password='qa-pass-strong', role='donor'
        )
        self.recipient = User.objects.create_user(
            username='qa-recipient', password='qa-pass-strong', role='recipient'
        )
        self.other_donor = User.objects.create_user(
            username='qa-other-donor', password='qa-pass-strong', role='donor'
        )
        self.donor_org = self.make_organization(
            'QA donor organization', 'restaurant'
        )
        self.recipient_org = self.make_organization(
            'QA recipient organization', 'ngo'
        )
        self.other_donor_org = self.make_organization(
            'QA unrelated donor organization', 'supermarket'
        )
        Membership.objects.create(
            user=self.donor, organization=self.donor_org, role='owner'
        )
        Membership.objects.create(
            user=self.recipient, organization=self.recipient_org, role='member'
        )
        Membership.objects.create(
            user=self.other_donor, organization=self.other_donor_org, role='owner'
        )

        self.donor_client = APIClient()
        self.donor_client.force_authenticate(user=self.donor)
        self.recipient_client = APIClient()
        self.recipient_client.force_authenticate(user=self.recipient)
        self.other_donor_client = APIClient()
        self.other_donor_client.force_authenticate(user=self.other_donor)

    def make_organization(self, name, org_type, status='verified'):
        return Organization.objects.create(
            name=name,
            org_type=org_type,
            address='1 QA Way',
            city='Test City',
            state='Test State',
            postal_code='00001',
            country='USA',
            phone='555-0100',
            email=f'{name.lower().replace(" ", "-")}@example.test',
            status=status,
        )

    def create_donation(self, *, title='QA workflow food', quantity='25.00', status='published'):
        now = timezone.now()
        return Donation.objects.create(
            donor=self.donor,
            organization=self.donor_org,
            title=title,
            description='Isolated QA workflow listing',
            food_category='produce',
            quantity=Decimal(quantity),
            unit='kg',
            available_from=now - timedelta(minutes=5),
            available_until=now + timedelta(days=2),
            pickup_address='1 QA Way',
            status=status,
        )

    def request_payload(self, donation, *, organization=None, quantity='8.00'):
        return {
            'donation': donation.pk,
            'organization': (organization or self.recipient_org).pk,
            'requested_quantity': quantity,
            'requested_unit': 'kg',
            'notes': 'Isolated browser workflow verification',
        }

    def submit_request(self, donation, *, organization=None, quantity='8.00'):
        return self.recipient_client.post(
            '/api/donation-requests/',
            self.request_payload(
                donation, organization=organization, quantity=quantity
            ),
            format='json',
        )

    def approve(self, request_id, *, quantity='8.00', idempotency_key='qa-allocation-1'):
        return self.donor_client.post(
            f'/api/donation-requests/{request_id}/approve/',
            {'approved_quantity': quantity, 'approved_unit': 'kg'},
            format='json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
