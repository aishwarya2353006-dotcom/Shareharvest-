from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .models import Membership, Organization


class OrganizationAdminTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Hope for All Foundation', org_type='ngo', address='1 Green Way',
            city='Example City', state='Example State', postal_code='10000',
            country='India', phone='555-0199', email='hope@example.test',
        )
        self.user_model = get_user_model()
        self.staff = self.user_model.objects.create_user(
            username='ordinary-staff', password='StrongPass123!', is_staff=True,
            role='donor',
        )
        self.platform_admin = self.user_model.objects.create_user(
            username='platform-admin-staff', password='StrongPass123!', is_staff=True,
            role='admin',
        )
        self._grant(self.staff, Organization, 'view_organization', 'change_organization')
        self._grant(self.staff, Membership, 'view_membership')
        self._grant(self.platform_admin, Organization, 'view_organization', 'change_organization')

    @staticmethod
    def _grant(user, model, *codenames):
        content_type = ContentType.objects.get_for_model(model)
        user.user_permissions.add(*Permission.objects.filter(
            content_type=content_type, codename__in=codenames,
        ))

    @staticmethod
    def _organization_form(status):
        return {
            'name': 'Hope for All Foundation', 'org_type': 'ngo', 'description': '',
            'address': '1 Green Way', 'city': 'Example City', 'state': 'Example State',
            'postal_code': '10000', 'country': 'India', 'phone': '555-0199',
            'email': 'hope@example.test', 'website': '', 'status': status,
            '_save': 'Save',
        }

    def test_admin_index_and_organization_search_include_models_and_pending_status(self):
        self.client.force_login(self.staff)
        index = self.client.get('/admin/')
        self.assertEqual(index.status_code, 200)
        self.assertContains(index, 'Organizations')
        self.assertContains(index, 'Memberships')

        changelist = self.client.get(reverse('admin:organizations_organization_changelist'))
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, 'Hope for All Foundation')
        self.assertContains(changelist, 'Pending Verification')

    def test_ordinary_staff_cannot_change_verification_even_with_change_permission(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('admin:organizations_organization_change', args=[self.organization.pk]),
            self._organization_form('verified'),
        )
        self.assertEqual(response.status_code, 302)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.status, 'pending')
        self.assertIsNone(self.organization.verified_by_id)
        self.assertIsNone(self.organization.verified_at)

    def test_platform_admin_staff_can_verify_and_membership_roles_are_not_editable(self):
        self.client.force_login(self.platform_admin)
        response = self.client.post(
            reverse('admin:organizations_organization_change', args=[self.organization.pk]),
            self._organization_form('verified'),
        )
        self.assertEqual(response.status_code, 302)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.status, 'verified')
        self.assertEqual(self.organization.verified_by_id, self.platform_admin.pk)
        self.assertIsNotNone(self.organization.verified_at)

        membership_admin = admin.site._registry[Membership]
        request = RequestFactory().get('/admin/organizations/membership/')
        request.user = self.platform_admin
        self.assertFalse(membership_admin.has_add_permission(request))
        self.assertFalse(membership_admin.has_change_permission(request))
        self.assertFalse(membership_admin.has_delete_permission(request))
