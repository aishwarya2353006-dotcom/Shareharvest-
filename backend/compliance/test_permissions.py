from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from organizations.models import Organization, Membership
from donations.models import Donation
from compliance.models import OrganizationCompliance, AllergenDeclaration, ComplianceDocument
from rest_framework import status

class CompliancePermissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='admin2', password='pass', role='admin')
        self.donor_a = User.objects.create_user(username='donor_a', password='pass', role='donor')
        self.donor_b = User.objects.create_user(username='donor_b', password='pass', role='donor')
        self.recipient = User.objects.create_user(username='recipient_x', password='pass', role='recipient')
        self.org_a = Organization.objects.create(
            name='Org A', org_type='ngo', address='1 St', city='City',
            state='State', postal_code='12345', country='India', phone='111',
            email='a@test.com'
        )
        self.org_b = Organization.objects.create(
            name='Org B', org_type='ngo', address='2 St', city='City',
            state='State', postal_code='12345', country='India', phone='222',
            email='b@test.com'
        )
        Membership.objects.create(user=self.donor_a, organization=self.org_a, role='owner', is_active=True)
        Membership.objects.create(user=self.donor_b, organization=self.org_b, role='owner', is_active=True)
        self.compliance_a = OrganizationCompliance.objects.create(
            organization=self.org_a, fssai_license_number='12345678901234',
            fssai_license_expiry=timezone.now().date() + timedelta(days=30),
            compliance_status='submitted'
        )
        self.compliance_b = OrganizationCompliance.objects.create(
            organization=self.org_b, fssai_license_number='43210987654321',
            fssai_license_expiry=timezone.now().date() + timedelta(days=30),
            compliance_status='submitted'
        )
        self.donation_a = Donation.objects.create(
            donor=self.donor_a, organization=self.org_a, title='Donation A',
            description='Desc', food_category='prepared', quantity=10, unit='kg',
            available_from=timezone.now(), available_until=timezone.now() + timedelta(days=1),
            pickup_address='1 A St'
        )
        self.allergen_a = AllergenDeclaration.objects.create(
            donation=self.donation_a, declared_by=self.donor_a,
            allergens_present=['peanuts']
        )
        self.doc_a = ComplianceDocument.objects.create(
            organization=self.org_a, document_type='fssai_license',
            file_path='/tmp/a.pdf', uploaded_by=self.donor_a
        )

    def test_unauthenticated_org_compliance_list(self):
        resp = self.client.get('/api/compliance/organization-compliance/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_unauthenticated_allergen_list(self):
        resp = self.client.get('/api/compliance/allergen-declarations/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_unauthenticated_compliance_document_list(self):
        resp = self.client.get('/api/compliance/compliance-documents/')
        self.assertIn(resp.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_donor_b_cannot_see_org_a_compliance(self):
        self.client.force_login(self.donor_b)
        resp = self.client.get('/api/compliance/organization-compliance/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in resp.json().get('results', [])]
        self.assertNotIn(self.compliance_a.id, ids)

    def test_donor_b_cannot_retrieve_org_a_compliance(self):
        self.client.force_login(self.donor_b)
        resp = self.client.get(f'/api/compliance/organization-compliance/{self.compliance_a.id}/')
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_donor_b_cannot_see_org_a_allergen(self):
        self.client.force_login(self.donor_b)
        resp = self.client.get('/api/compliance/allergen-declarations/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in resp.json().get('results', [])]
        self.assertNotIn(self.allergen_a.id, ids)

    def test_donor_b_cannot_see_org_a_compliance_doc(self):
        self.client.force_login(self.donor_b)
        resp = self.client.get('/api/compliance/compliance-documents/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in resp.json().get('results', [])]
        self.assertNotIn(self.doc_a.id, ids)

    def test_donor_b_cannot_create_compliance_for_org_a(self):
        self.client.force_login(self.donor_b)
        resp = self.client.post('/api/compliance/organization-compliance/', {
            'organization': self.org_a.id,
            'fssai_license_number': '99999999999999',
            'fssai_license_expiry': '2027-01-01',
        }, format='json')
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])

    def test_regular_member_cannot_create_compliance(self):
        member = User.objects.create_user(username='member_x', password='pass', role='donor')
        Membership.objects.create(user=member, organization=self.org_a, role='member', is_active=True)
        self.client.force_login(member)
        resp = self.client.post('/api/compliance/organization-compliance/', {
            'fssai_license_number': '99999999999999',
            'fssai_license_expiry': '2027-01-01',
        }, format='json')
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])

    def test_donor_a_can_create_compliance_for_own_org(self):
        # Org A already has compliance, so create for a new org
        new_org = Organization.objects.create(
            name='Org C', org_type='ngo', address='3 St', city='City',
            state='State', postal_code='12345', country='India', phone='333',
            email='c@test.com'
        )
        Membership.objects.create(user=self.donor_a, organization=new_org, role='owner', is_active=True)
        self.client.force_login(self.donor_a)
        resp = self.client.post('/api/compliance/organization-compliance/', {
            'organization': new_org.id,
            'fssai_license_number': '55555555555555',
            'fssai_license_expiry': '2027-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_verify_reject_require_admin(self):
        self.client.force_login(self.donor_a)
        resp = self.client.post(
            f'/api/compliance/organization-compliance/{self.compliance_a.id}/verify/',
            {'action': 'verify'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_allergen_review_requires_admin(self):
        self.client.force_login(self.donor_a)
        resp = self.client.post(
            f'/api/compliance/allergen-declarations/{self.allergen_a.id}/verify/',
            {'action': 'verify'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_fssai_license_rejected(self):
        new_org = Organization.objects.create(
            name='Org D', org_type='ngo', address='4 St', city='City',
            state='State', postal_code='12345', country='India', phone='444',
            email='d@test.com'
        )
        Membership.objects.create(user=self.donor_a, organization=new_org, role='owner', is_active=True)
        self.client.force_login(self.donor_a)
        resp = self.client.post('/api/compliance/organization-compliance/', {
            'organization': new_org.id,
            'fssai_license_number': '123',  # too short
            'fssai_license_expiry': '2027-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compliance_document_create_requires_org_membership(self):
        self.client.force_login(self.donor_b)
        resp = self.client.post('/api/compliance/compliance-documents/', {
            'organization': self.org_a.id,
            'document_type': 'fssai_license',
            'file_path': '/tmp/b.pdf',
        }, format='json')
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])

    def test_readonly_verify_rejects_write_on_org_compliance(self):
        # OrganizationComplianceViewSet is ModelViewSet but update/partial_update
        # are not restricted by get_permissions beyond IsAuthenticated.
        # Test that a non-owner cannot update another org's compliance.
        self.client.force_login(self.donor_b)
        resp = self.client.patch(
            f'/api/compliance/organization-compliance/{self.compliance_a.id}/',
            {'notes': 'hacked'}, format='json'
        )
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])
