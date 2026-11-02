from uuid import uuid4

from rest_framework import status
from rest_framework.test import APIClient

from donation_requests.models import DonationAllocation
from .support import DonationWorkflowTestCase


class WorkflowAuthorizationTests(DonationWorkflowTestCase):
    def test_recipient_and_unrelated_donor_cannot_approve_or_reject(self):
        donation = self.create_donation()
        created = self.submit_request(donation)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        request_id = created.data['id']
        body = {'approved_quantity': '1.00', 'approved_unit': 'kg'}

        forbidden_approval = self.recipient_client.post(
            f'/api/donation-requests/{request_id}/approve/',
            body,
            format='json',
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(
            forbidden_approval.status_code,
            status.HTTP_403_FORBIDDEN,
            forbidden_approval.data,
        )
        forbidden_rejection = self.recipient_client.post(
            f'/api/donation-requests/{request_id}/reject/', {}, format='json'
        )
        self.assertEqual(
            forbidden_rejection.status_code,
            status.HTTP_403_FORBIDDEN,
            forbidden_rejection.data,
        )

        hidden_approval = self.other_donor_client.post(
            f'/api/donation-requests/{request_id}/approve/',
            body,
            format='json',
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(hidden_approval.status_code, status.HTTP_404_NOT_FOUND)
        hidden_rejection = self.other_donor_client.post(
            f'/api/donation-requests/{request_id}/reject/', {}, format='json'
        )
        self.assertEqual(hidden_rejection.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(DonationAllocation.objects.count(), 0)

    def test_unauthenticated_request_and_review_are_rejected(self):
        donation = self.create_donation()
        created = self.submit_request(donation)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        anonymous = APIClient()
        request_id = created.data['id']

        self.assertEqual(
            anonymous.post(
                '/api/donation-requests/',
                self.request_payload(donation),
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            anonymous.post(
                f'/api/donation-requests/{request_id}/approve/',
                {'approved_quantity': '1', 'approved_unit': 'kg'},
                format='json',
                HTTP_IDEMPOTENCY_KEY=uuid4().hex,
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
