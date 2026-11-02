from django.test import TestCase, Client
from unittest.mock import patch
from audit.models import AuditLog
from audit.services import log_audit
from accounts.models import User
from rest_framework import status

class AuditReliabilityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='admin_ar', password='pass', role='admin')

    def test_log_audit_swallows_exceptions(self):
        # Verify that log_audit does not raise even when AuditLog.objects.create fails
        with patch('audit.services.AuditLog.objects.create', side_effect=Exception('DB error')):
            # Should not raise
            log_audit(user=self.admin, action='create', object_type='Test', object_id=1)
        # No audit record created
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_compliance_create_produces_audit_record(self):
        from organizations.models import Organization, Membership
        org = Organization.objects.create(
            name='Org AR', org_type='ngo', address='1 St', city='City',
            state='State', postal_code='12345', country='India', phone='111',
            email='ar@test.com'
        )
        Membership.objects.create(user=self.admin, organization=org, role='owner', is_active=True)
        self.client.force_login(self.admin)
        self.client.post('/api/compliance/organization-compliance/', {
            'organization': org.id,
            'fssai_license_number': '12345678901234',
            'fssai_license_expiry': '2027-01-01',
        }, format='json')
        self.assertEqual(AuditLog.objects.filter(object_type='organization_compliance').count(), 1)

    def test_donation_create_does_not_produce_audit_record(self):
        from organizations.models import Organization, Membership
        from donations.models import Donation
        from django.utils import timezone
        from datetime import timedelta
        org = Organization.objects.create(
            name='Org AR2', org_type='restaurant', address='1 St', city='City',
            state='State', postal_code='12345', country='USA', phone='111',
            email='ar2@test.com', status='verified'
        )
        Membership.objects.create(user=self.admin, organization=org, role='owner', is_active=True)
        before = AuditLog.objects.count()
        self.client.force_login(self.admin)
        self.client.post('/api/donations/donations/', {
            'title': 'Test Donation', 'description': 'Desc', 'food_category': 'prepared',
            'quantity': 10, 'unit': 'kg',
            'available_from': (timezone.now()).isoformat(),
            'available_until': (timezone.now() + timedelta(days=1)).isoformat(),
            'pickup_address': '123 St', 'organization': org.id
        }, format='json')
        after = AuditLog.objects.count()
        # Donation creation does NOT produce audit record (confirmed gap)
        self.assertEqual(before, after)
