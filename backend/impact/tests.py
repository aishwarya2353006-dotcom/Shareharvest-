from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from rest_framework import status

from impact.serializers import ImpactReportSerializer
from impact.models import ImpactReport
from organizations.models import Organization


class ImpactSerializerTests(TestCase):
    def test_serializer_model_fields(self):
        org = Organization.objects.create(name='Test Org', org_type='ngo', address='addr', city='city', state='state')
        report = ImpactReport.objects.create(
            organization=org,
            period_type='monthly',
            start_date='2026-01-01',
            end_date='2026-01-31',
            total_donations=5,
            total_quantity_kg=Decimal('10.50'),
            total_recipients_served=3,
        )
        serializer = ImpactReportSerializer(report)
        data = serializer.data
        self.assertEqual(data['period_type'], 'monthly')
        self.assertEqual(data['total_donations'], 5)
        self.assertIn('organization', data)
        self.assertIn('created_at', data)


class ImpactSummaryEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='impact-user', password='StrongPass123!', role='recipient'
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.get('/api/accounts/csrf_token/')
        token = self.client.cookies['csrftoken'].value
        self.client.post(
            '/api/accounts/login/',
            data={'username': 'impact-user', 'password': 'StrongPass123!'},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN='http://localhost:5173',
        )

    def test_summary_returns_expected_structure(self):
        response = self.client.get('/api/impact/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        data = response.json()
        self.assertIn('completed_pickups', data)
        self.assertIn('total_allocated_kg', data)
        self.assertIn('donations_published', data)
        self.assertIn('organizations', data)

    def test_summary_unauthenticated(self):
        client = Client()
        response = client.get('/api/impact/summary/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
