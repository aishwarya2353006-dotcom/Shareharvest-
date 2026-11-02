from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from audit.models import AuditLog
from donations.models import Donation
from organizations.models import Membership, Organization

from .models import AllergenDeclaration, OrganizationCompliance


class ComplianceAdminApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='platform-admin', password='StrongPass123!', role='admin'
        )
        self.donor = User.objects.create_user(
            username='donor', password='StrongPass123!', role='donor'
        )
        self.recipient = User.objects.create_user(
            username='recipient', password='StrongPass123!', role='recipient'
        )
        self.organization = self.create_organization('Donor organization')
        self.other_organization = self.create_organization('Other organization')
        Membership.objects.create(
            user=self.donor, organization=self.organization, role='owner'
        )
        self.compliance = OrganizationCompliance.objects.create(
            organization=self.organization,
            fssai_license_number='12345678901234',
            fssai_license_expiry=timezone.now().date() + timedelta(days=30),
            compliance_status='submitted',
        )
        self.other_compliance = OrganizationCompliance.objects.create(
            organization=self.other_organization,
            fssai_license_number='43210987654321',
            fssai_license_expiry=timezone.now().date() + timedelta(days=30),
            compliance_status='submitted',
        )
        self.donation = self.create_donation(self.organization, self.donor)
        self.allergen = AllergenDeclaration.objects.create(
            donation=self.donation,
            declared_by=self.donor,
            allergens_present=['peanuts'],
            cross_contamination_risk=True,
            cross_contamination_details='Prepared in a shared kitchen.',
        )

    @staticmethod
    def create_organization(name):
        return Organization.objects.create(
            name=name, org_type='ngo', address='1 Green Way', city='Example City',
            state='Example State', postal_code='10000', country='India',
            phone='555-0199', email=f'{name.lower().replace(" ", "-")}@example.test',
        )

    @staticmethod
    def create_donation(organization, donor):
        now = timezone.now()
        return Donation.objects.create(
            organization=organization, donor=donor, title='Surplus meals',
            description='Freshly prepared meals', food_category='prepared',
            quantity='10.00', unit='kg', available_from=now,
            available_until=now + timedelta(days=1), pickup_address='1 Green Way',
        )

    def test_compliance_lists_follow_role_and_organization_scope(self):
        self.client.force_authenticate(user=self.admin)
        admin_response = self.client.get('/api/compliance/organization-compliance/')
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_response.data['count'], 2)

        self.client.force_authenticate(user=self.donor)
        donor_response = self.client.get('/api/compliance/organization-compliance/')
        self.assertEqual(donor_response.status_code, status.HTTP_200_OK)
        self.assertEqual(donor_response.data['count'], 1)
        self.assertEqual(
            donor_response.data['results'][0]['organization'], self.organization.pk
        )

        allergen_response = self.client.get('/api/compliance/allergen-declarations/')
        self.assertEqual(allergen_response.status_code, status.HTTP_200_OK)
        self.assertEqual(allergen_response.data['count'], 1)

    def test_only_platform_admin_can_verify_or_reject_compliance(self):
        self.client.force_authenticate(user=self.recipient)
        forbidden = self.client.post(
            f'/api/compliance/organization-compliance/{self.compliance.pk}/verify/',
            {'action': 'verify'},
            format='json',
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin)
        blank_reason = self.client.post(
            f'/api/compliance/organization-compliance/{self.compliance.pk}/reject/',
            {'action': 'reject', 'rejection_reason': '   '},
            format='json',
        )
        self.assertEqual(blank_reason.status_code, status.HTTP_400_BAD_REQUEST)
        self.compliance.refresh_from_db()
        self.assertEqual(self.compliance.compliance_status, 'submitted')

        rejected = self.client.post(
            f'/api/compliance/organization-compliance/{self.compliance.pk}/reject/',
            {'action': 'reject', 'rejection_reason': 'License image is unreadable.'},
            format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        self.assertEqual(rejected.data['compliance_status'], 'rejected')
        self.assertEqual(rejected.data['rejection_reason'], 'License image is unreadable.')

        verified = self.client.post(
            f'/api/compliance/organization-compliance/{self.other_compliance.pk}/verify/',
            {'action': 'verify'},
            format='json',
        )
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        self.assertEqual(verified.data['compliance_status'], 'verified')
        self.assertEqual(
            AuditLog.objects.filter(
                user=self.admin, object_type='organization_compliance',
                action__in=['verify', 'reject'],
            ).count(),
            2,
        )

    def test_allergen_review_actions_require_platform_admin_and_record_audit(self):
        self.client.force_authenticate(user=self.donor)
        forbidden = self.client.post(
            f'/api/compliance/allergen-declarations/{self.allergen.pk}/verify/',
            {'action': 'verify'},
            format='json',
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin)
        verified = self.client.post(
            f'/api/compliance/allergen-declarations/{self.allergen.pk}/verify/',
            {'action': 'verify'},
            format='json',
        )
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        self.assertEqual(verified.data['declaration_status'], 'verified')

        rejected_donation = self.create_donation(self.organization, self.donor)
        rejected_allergen = AllergenDeclaration.objects.create(
            donation=rejected_donation,
            declared_by=self.donor,
            allergens_present=['milk'],
        )
        blank_reason = self.client.post(
            f'/api/compliance/allergen-declarations/{rejected_allergen.pk}/reject/',
            {'action': 'reject', 'review_notes': '   '},
            format='json',
        )
        self.assertEqual(blank_reason.status_code, status.HTTP_400_BAD_REQUEST)
        rejected = self.client.post(
            f'/api/compliance/allergen-declarations/{rejected_allergen.pk}/reject/',
            {'action': 'reject', 'review_notes': 'Please confirm the ingredient source.'},
            format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        self.assertEqual(rejected.data['declaration_status'], 'rejected')
        self.assertEqual(
            rejected.data['review_notes'], 'Please confirm the ingredient source.'
        )
        self.assertEqual(
            AuditLog.objects.filter(
                user=self.admin, object_type='allergen_declaration',
                action__in=['verify', 'reject'],
            ).count(),
            2,
        )
