from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.utils import timezone
from rest_framework import status

from donation_requests.models import DonationAllocation, DonationRequest
from donation_requests.services import donation_remaining_base
from .support import DonationWorkflowTestCase


class RequestBoundaryTests(DonationWorkflowTestCase):
    def test_invalid_quantities_excess_stock_and_missing_quantity_are_rejected(self):
        donation = self.create_donation()
        initial_count = DonationRequest.objects.count()
        for quantity in ('0', '-1', '25.01', 'not-a-number'):
            response = self.submit_request(donation, quantity=quantity)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        missing = self.recipient_client.post(
            '/api/donation-requests/',
            {
                'donation': donation.pk,
                'organization': self.recipient_org.pk,
                'requested_unit': 'kg',
            },
            format='json',
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST, missing.data)
        self.assertEqual(DonationRequest.objects.count(), initial_count)
        self.assertEqual(donation_remaining_base(donation), Decimal('25000.00'))

    def test_unpublished_expired_and_own_organization_offers_are_rejected(self):
        draft = self.create_donation(title='QA draft', status='draft')
        self.assertEqual(
            self.submit_request(draft).status_code, status.HTTP_400_BAD_REQUEST
        )

        expired = self.create_donation(title='QA expired')
        expired.available_until = timezone.now() - timedelta(minutes=1)
        expired.save()
        self.assertEqual(
            self.submit_request(expired).status_code, status.HTTP_400_BAD_REQUEST
        )

        own_org_donation = self.create_donation(title='QA own organization')
        own_org_donation.organization = self.recipient_org
        own_org_donation.save()
        self.assertEqual(
            self.submit_request(own_org_donation).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(DonationRequest.objects.count(), 0)
        self.assertEqual(DonationAllocation.objects.count(), 0)

    def test_duplicate_open_request_and_oversized_approval_fail_without_changes(self):
        donation = self.create_donation()
        first = self.submit_request(donation, quantity='10.00')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        duplicate = self.submit_request(donation, quantity='2.00')
        self.assertEqual(duplicate.status_code, status.HTTP_409_CONFLICT, duplicate.data)

        before = donation_remaining_base(donation)
        oversized = self.approve(
            first.data['id'], quantity='10.01', idempotency_key=uuid4().hex
        )
        self.assertEqual(oversized.status_code, status.HTTP_409_CONFLICT, oversized.data)
        self.assertEqual(DonationAllocation.objects.count(), 0)
        self.assertEqual(donation_remaining_base(donation), before)
        request_obj = DonationRequest.objects.get(pk=first.data['id'])
        self.assertEqual(request_obj.status, 'pending')
