from decimal import Decimal
from uuid import uuid4

from django.test import override_settings
from rest_framework import status

from donation_requests.models import DonationAllocation
from donation_requests.services import donation_remaining_base
from donations.models import Donation
from .support import DonationWorkflowTestCase


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'])
class BrowserWorkflowPersistenceTests(DonationWorkflowTestCase):
    def test_recipient_browse_returns_paginated_available_donations(self):
        donation = self.create_donation()

        response = self.recipient_client.get(
            '/api/donations/donations/?browse=true'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertSetEqual(
            set(response.data),
            {'count', 'next', 'previous', 'results'},
        )
        self.assertEqual(response.data['count'], 1)
        self.assertIsNone(response.data['next'])
        self.assertIsNone(response.data['previous'])
        self.assertEqual(len(response.data['results']), 1)
        result = response.data['results'][0]
        self.assertEqual(result['id'], donation.pk)
        self.assertEqual(result['title'], donation.title)
        self.assertEqual(result['status'], 'published')

    def test_create_publish_request_partial_approval_persists_inventory(self):
        created = self.donor_client.post(
            '/api/donations/donations/',
            {
                'organization': self.donor_org.pk,
                'title': f'QA approval {uuid4().hex}',
                'description': 'Unique approval workflow listing',
                'food_category': 'produce',
                'quantity': '25.00',
                'unit': 'kg',
                'available_from': '2026-10-01T00:00:00Z',
                'available_until': '2027-10-01T00:00:00Z',
                'pickup_address': '1 QA Way',
            },
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        donation_id = created.data['id']
        published = self.donor_client.patch(
            f'/api/donations/donations/{donation_id}/',
            {'status': 'published'},
            format='json',
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK, published.data)
        self.assertEqual(published.data['status'], 'published')
        self.assertEqual(Decimal(published.data['quantity']), Decimal('25.00'))

        browse = self.recipient_client.get('/api/donations/donations/?browse=true')
        self.assertEqual(browse.status_code, status.HTTP_200_OK, browse.data)
        self.assertIn(donation_id, [item['id'] for item in browse.data['results']])
        request_response = self.submit_request(
            Donation.objects.get(pk=donation_id)
        )
        self.assertEqual(
            request_response.status_code, status.HTTP_201_CREATED, request_response.data
        )
        request_id = request_response.data['id']
        self.assertEqual(request_response.data['status'], 'pending')

        donor_list = self.donor_client.get(
            f'/api/donation-requests/?donation={donation_id}'
        )
        self.assertEqual(donor_list.status_code, status.HTTP_200_OK)
        self.assertEqual(donor_list.data['results'][0]['status'], 'pending')

        approved = self.approve(
            request_id, quantity='8.00', idempotency_key=uuid4().hex
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)
        self.assertEqual(approved.data['status'], 'approved')
        self.assertEqual(Decimal(approved.data['approved_quantity']), Decimal('8'))
        self.assertEqual(Decimal(approved.data['remaining_quantity']), Decimal('0'))

        recipient_list = self.recipient_client.get(
            '/api/donation-requests/?mine=true'
        )
        self.assertEqual(recipient_list.status_code, status.HTTP_200_OK)
        recipient_request = recipient_list.data['results'][0]
        self.assertEqual(recipient_request['status'], 'approved')
        self.assertEqual(Decimal(recipient_request['approved_quantity']), Decimal('8'))

        donation = Donation.objects.get(pk=donation_id)
        self.assertEqual(donation.quantity, Decimal('25.00'))
        self.assertEqual(donation.allocated_quantity_kg, Decimal('8.000'))
        self.assertEqual(donation_remaining_base(donation), Decimal('17000.00'))
        self.assertEqual(
            DonationAllocation.objects.filter(request_id=request_id).count(), 1
        )

    def test_rejection_does_not_consume_or_allocate_stock(self):
        donation = self.create_donation(title=f'QA rejection {uuid4().hex}')
        created = self.submit_request(donation, quantity='8.00')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        request_id = created.data['id']

        rejected = self.donor_client.post(
            f'/api/donation-requests/{request_id}/reject/', {}, format='json'
        )
        self.assertEqual(rejected.status_code, status.HTTP_200_OK, rejected.data)
        self.assertEqual(rejected.data['status'], 'rejected')
        self.assertEqual(DonationAllocation.objects.filter(request_id=request_id).count(), 0)

        donation.refresh_from_db()
        self.assertEqual(donation.quantity, Decimal('25.00'))
        self.assertEqual(donation.allocated_quantity_kg, Decimal('0'))
        self.assertEqual(donation_remaining_base(donation), Decimal('25000.00'))

        recipient_list = self.recipient_client.get(
            '/api/donation-requests/?mine=true'
        )
        self.assertEqual(recipient_list.status_code, status.HTTP_200_OK)
        self.assertEqual(recipient_list.data['results'][0]['status'], 'rejected')
