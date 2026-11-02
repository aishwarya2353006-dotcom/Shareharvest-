import json
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, Client
from django.utils import timezone
from organizations.models import Organization, Membership
from accounts.models import User
from donations.models import Donation
from donation_requests.models import DonationAllocation, DonationRequest
from pickups.models import Pickup
from rest_framework import status

class OrganizationViewSetTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')
        self.admin_user = User.objects.create_user(username='admin', password='pass', role='admin')

    def test_organization_creation_and_owner_membership(self):
        # User1 creates an organization
        self.client.force_login(self.user1)
        response = self.client.post('/api/organizations/organizations/', {
            'name': 'Test Org',
            'org_type': 'restaurant',
            'address': '123 Main St',
            'city': 'City',
            'state': 'State',
            'postal_code': '12345',
            'country': 'USA',
            'phone': '123-456-7890',
            'email': 'test@example.com'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Organization.objects.filter(name='Test Org').exists())
        org = Organization.objects.get(name='Test Org')
        self.assertTrue(Membership.objects.filter(user=self.user1, organization=org, role='owner', is_active=True).exists())

    def test_organization_listing_isolation(self):
        # Create two organizations: one for user1 and one for user2
        self.client.force_login(self.user1)
        resp1 = self.client.post('/api/organizations/organizations/', {
            'name': 'Org1',
            'org_type': 'restaurant',
            'address': '123 Main St',
            'city': 'City',
            'state': 'State',
            'postal_code': '12345',
            'country': 'USA',
            'phone': '123-456-7890',
            'email': 'test1@example.com'
        }, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        self.client.force_login(self.user2)
        resp2 = self.client.post('/api/organizations/organizations/', {
            'name': 'Org2',
            'org_type': 'hotel',
            'address': '456 Oak Ave',
            'city': 'City',
            'state': 'State',
            'postal_code': '12345',
            'country': 'USA',
            'phone': '098-765-4321',
            'email': 'test2@example.com'
        }, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED)

        # Now test that user1 can only see Org1
        self.client.force_login(self.user1)
        response = self.client.get('/api/organizations/organizations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['name'], 'Org1')

        # User2 can only see Org2
        self.client.force_login(self.user2)
        response = self.client.get('/api/organizations/organizations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['name'], 'Org2')

        # Admin user can see both
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/organizations/organizations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 2)
        self.assertEqual(len(data['results']), 2)
        org_names = {org['name'] for org in data['results']}
        self.assertEqual(org_names, {'Org1', 'Org2'})

    def test_manager_membership_scope_and_role_hierarchy(self):
        organization = Organization.objects.create(
            name='Managed Org', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', country='USA', phone='1', email='managed@example.com',
            status='verified',
        )
        owner = Membership.objects.create(user=self.user1, organization=organization, role='owner')
        member = Membership.objects.create(user=self.user2, organization=organization, role='member')

        self.client.force_login(self.user1)
        listed = self.client.get(f'/api/organizations/memberships/?organization={organization.id}')
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.json()['count'], 2)

        last_owner_role_change = self.client.patch(
            f'/api/organizations/memberships/{owner.id}/?organization={organization.id}',
            data=json.dumps({'role': 'member'}), content_type='application/json',
        )
        self.assertEqual(last_owner_role_change.status_code, status.HTTP_400_BAD_REQUEST)
        last_owner_deactivation = self.client.patch(
            f'/api/organizations/memberships/{owner.id}/?organization={organization.id}',
            data=json.dumps({'is_active': False}), content_type='application/json',
        )
        self.assertEqual(last_owner_deactivation.status_code, status.HTTP_400_BAD_REQUEST)
        last_owner_deletion = self.client.delete(
            f'/api/organizations/memberships/{owner.id}/?organization={organization.id}'
        )
        self.assertEqual(last_owner_deletion.status_code, status.HTTP_400_BAD_REQUEST)

        changed = self.client.patch(
            f'/api/organizations/memberships/{member.id}/?organization={organization.id}',
            data=json.dumps({'role': 'volunteer'}), content_type='application/json',
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK, changed.content)
        self.assertEqual(changed.json()['role'], 'volunteer')
        self.assertEqual(changed.json()['user'], self.user2.id)
        self.assertEqual(changed.json()['organization'], organization.id)
        self.assertTrue(changed.json()['is_active'])

        self.client.force_login(self.user2)
        promoted = self.client.patch(
            f'/api/organizations/memberships/{member.id}/',
            data=json.dumps({'role': 'owner'}), content_type='application/json',
        )
        self.assertEqual(promoted.status_code, status.HTTP_403_FORBIDDEN)
        owner.refresh_from_db()
        self.assertEqual(owner.role, 'owner')

    def test_only_managers_can_add_members_and_inactive_user_cannot_reactivate_self(self):
        organization = Organization.objects.create(
            name='Membership Org', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', country='USA', phone='1', email='membership@example.com',
            status='verified',
        )
        Membership.objects.create(user=self.user1, organization=organization, role='member')
        inactive_user = User.objects.create_user(username='inactive-user', password='pass')
        inactive_membership = Membership.objects.create(
            user=inactive_user, organization=organization, role='member', is_active=False,
        )
        new_user = User.objects.create_user(username='new-member', password='pass')

        self.client.force_login(self.user1)
        create_response = self.client.post(
            '/api/organizations/memberships/',
            data=json.dumps({'user': new_user.id, 'organization': organization.id, 'role': 'volunteer'}),
            content_type='application/json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_login(inactive_user)
        reactivate_response = self.client.patch(
            f'/api/organizations/memberships/{inactive_membership.id}/',
            data=json.dumps({'is_active': True}), content_type='application/json',
        )
        self.assertEqual(reactivate_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_add_existing_user_and_duplicate_requires_reactivation(self):
        organization = Organization.objects.create(
            name='Add member org', org_type='restaurant', address='A', city='C',
            state='S', postal_code='1', country='USA', phone='1',
            email='add-member@example.com', status='verified',
        )
        Membership.objects.create(user=self.user1, organization=organization, role='owner')
        existing_user = User.objects.create_user(username='existing-user', password='pass')
        self.client.force_login(self.user1)

        payload = {
            'user': existing_user.id,
            'organization': organization.id,
            'role': 'volunteer',
        }
        created = self.client.post(
            '/api/organizations/memberships/',
            data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.content)
        self.assertEqual(created.json()['user'], existing_user.id)
        self.assertEqual(created.json()['role'], 'volunteer')

        duplicate = self.client.post(
            '/api/organizations/memberships/',
            data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('active membership', str(duplicate.json()).lower())

        inactive_user = User.objects.create_user(username='inactive-existing-user', password='pass')
        inactive_membership = Membership.objects.create(
            user=inactive_user, organization=organization, role='member', is_active=False,
        )
        payload.update(user=inactive_user.id, role='volunteer')
        inactive_duplicate = self.client.post(
            '/api/organizations/memberships/',
            data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(inactive_duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reactivate', str(inactive_duplicate.json()).lower())

        reactivated = self.client.patch(
            f'/api/organizations/memberships/{inactive_membership.id}/?organization={organization.id}',
            data=json.dumps({'is_active': True, 'role': 'volunteer'}),
            content_type='application/json',
        )
        self.assertEqual(reactivated.status_code, status.HTTP_200_OK, reactivated.content)
        self.assertTrue(reactivated.json()['is_active'])
        self.assertEqual(reactivated.json()['role'], 'volunteer')

    def test_organization_admin_cannot_assign_owner_when_adding_member(self):
        organization = Organization.objects.create(
            name='Role hierarchy org', org_type='restaurant', address='A', city='C',
            state='S', postal_code='1', country='USA', phone='1',
            email='role-hierarchy@example.com',
        )
        Membership.objects.create(user=self.user1, organization=organization, role='owner')
        Membership.objects.create(user=self.user2, organization=organization, role='admin')
        new_user = User.objects.create_user(username='new-hierarchy-member', password='pass')
        self.client.force_login(self.user2)

        payload = {'user': new_user.id, 'organization': organization.id, 'role': 'owner'}
        forbidden = self.client.post(
            '/api/organizations/memberships/',
            data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        payload['role'] = 'member'
        allowed = self.client.post(
            '/api/organizations/memberships/',
            data=json.dumps(payload), content_type='application/json',
        )
        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED, allowed.content)
        self.assertEqual(allowed.json()['role'], 'member')

    def test_membership_user_search_is_scoped_limited_and_minimizes_data(self):
        organization = Organization.objects.create(
            name='Search org', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', country='USA', phone='1', email='search-org@example.com',
        )
        Membership.objects.create(user=self.user1, organization=organization, role='owner')
        active_member = User.objects.create_user(
            username='already-active', password='pass', email='active@example.test',
        )
        Membership.objects.create(
            user=active_member, organization=organization, role='member', is_active=True,
        )
        inactive_member = User.objects.create_user(
            username='inactive-match', password='pass', email='inactive-match@example.test',
        )
        Membership.objects.create(
            user=inactive_member, organization=organization, role='member', is_active=False,
        )
        username_match = User.objects.create_user(
            username='HarvestVolunteer', password='pass', email='volunteer@example.test',
            phone='555-0100', first_name='Private',
        )
        email_match = User.objects.create_user(
            username='community-helper', password='pass', email='helper-search@example.test',
        )

        self.client.force_login(self.user1)
        by_username = self.client.get(
            f'/api/organizations/organizations/{organization.id}/user-search/?search=harvestvol'
        )
        self.assertEqual(by_username.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in by_username.json()], [username_match.id])
        self.assertEqual(set(by_username.json()[0]), {'id', 'username', 'email'})
        self.assertNotIn('phone', by_username.json()[0])
        self.assertNotIn('first_name', by_username.json()[0])

        by_email = self.client.get(
            f'/api/organizations/organizations/{organization.id}/user-search/?search=helper-search@'
        )
        self.assertEqual(by_email.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in by_email.json()], [email_match.id])
        self.assertEqual(
            self.client.get(
                f'/api/organizations/organizations/{organization.id}/user-search/?search=h'
            ).json(),
            [],
        )

        self.assertNotIn(active_member.id, [item['id'] for item in self.client.get(
            f'/api/organizations/organizations/{organization.id}/user-search/?search=already-active'
        ).json()])
        self.assertIn(inactive_member.id, [item['id'] for item in self.client.get(
            f'/api/organizations/organizations/{organization.id}/user-search/?search=inactive-match'
        ).json()])

        for index in range(12):
            User.objects.create_user(
                username=f'limit-search-{index:02}', password='pass',
                email=f'limit-search-{index:02}@example.test',
            )
        limited = self.client.get(
            f'/api/organizations/organizations/{organization.id}/user-search/?search=limit-search'
        )
        self.assertLessEqual(len(limited.json()), 10)

    def test_non_manager_cannot_search_users_for_organization(self):
        organization = Organization.objects.create(
            name='Private search org', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', country='USA', phone='1', email='private-search@example.com',
        )
        Membership.objects.create(user=self.user1, organization=organization, role='owner')
        Membership.objects.create(user=self.user2, organization=organization, role='member')
        self.client.force_login(self.user2)
        response = self.client.get(
            f'/api/organizations/organizations/{organization.id}/user-search/?search=some-user'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_only_platform_admin_can_change_verification_status(self):
        organization = Organization.objects.create(
            name='Pending Org', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', country='USA', phone='1', email='pending@example.com',
            status='pending',
        )
        Membership.objects.create(user=self.user1, organization=organization, role='owner')

        self.client.force_login(self.user1)
        forbidden = self.client.post(f'/api/organizations/organizations/{organization.id}/verify/')
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_login(self.admin_user)
        allowed = self.client.post(f'/api/organizations/organizations/{organization.id}/verify/')
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(allowed.json()['status'], 'verified')

    def test_only_platform_admin_can_reject_organization(self):
        organization = Organization.objects.create(
            name='Rejected Org', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', country='USA', phone='1', email='rejected@example.com',
            status='pending',
        )
        Membership.objects.create(user=self.user1, organization=organization, role='owner')

        self.client.force_login(self.user1)
        forbidden = self.client.post(
            f'/api/organizations/organizations/{organization.id}/reject/'
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_login(self.admin_user)
        rejected = self.client.post(
            f'/api/organizations/organizations/{organization.id}/reject/'
        )
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        self.assertEqual(rejected.json()['status'], 'rejected')
        organization.refresh_from_db()
        self.assertEqual(organization.verified_by, self.admin_user)

    def test_only_active_organization_managers_can_update_profile(self):
        organization = Organization.objects.create(
            name='Protected Org', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', country='USA', phone='1', email='protected@example.com',
        )
        Membership.objects.create(
            user=self.user1, organization=organization, role='owner'
        )
        Membership.objects.create(
            user=self.user2, organization=organization, role='member'
        )
        org_admin = User.objects.create_user(
            username='organization-admin', password='pass'
        )
        Membership.objects.create(
            user=org_admin, organization=organization, role='admin'
        )
        inactive_user = User.objects.create_user(
            username='inactive-manager', password='pass'
        )
        inactive_membership = Membership.objects.create(
            user=inactive_user, organization=organization, role='admin',
            is_active=False,
        )

        self.client.force_login(self.user2)
        member_update = self.client.patch(
            f'/api/organizations/organizations/{organization.id}/',
            data=json.dumps({'name': 'Changed by member'}),
            content_type='application/json',
        )
        self.assertEqual(member_update.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.patch(
                f'/api/organizations/organizations/{organization.id}/',
                data=json.dumps({'name': 'Privilege escalation', 'role': 'owner'}),
                content_type='application/json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        organization.refresh_from_db()
        self.assertEqual(organization.name, 'Protected Org')
        self.assertEqual(
            Membership.objects.get(user=self.user2, organization=organization).role,
            'member',
        )

        self.client.force_login(inactive_user)
        inactive_update = self.client.patch(
            f'/api/organizations/organizations/{organization.id}/',
            data=json.dumps({'name': 'Changed by inactive member'}),
            content_type='application/json',
        )
        self.assertEqual(inactive_update.status_code, status.HTTP_404_NOT_FOUND)
        inactive_membership.refresh_from_db()
        self.assertFalse(inactive_membership.is_active)

        self.client.force_login(self.user1)
        owner_update = self.client.patch(
            f'/api/organizations/organizations/{organization.id}/',
            data=json.dumps({'name': 'Updated by owner', 'phone': '555-0101'}),
            content_type='application/json',
        )
        self.assertEqual(owner_update.status_code, status.HTTP_200_OK)
        self.assertEqual(owner_update.json()['name'], 'Updated by owner')
        self.assertEqual(owner_update.json()['phone'], '555-0101')

        self.client.force_login(org_admin)
        manager_update = self.client.patch(
            f'/api/organizations/organizations/{organization.id}/',
            data=json.dumps({'description': 'Updated by organization admin'}),
            content_type='application/json',
        )
        self.assertEqual(manager_update.status_code, status.HTTP_200_OK)
        self.assertEqual(
            manager_update.json()['description'], 'Updated by organization admin'
        )

    def test_organization_detail_remains_scoped_and_admin_has_explicit_read_access(self):
        organization = Organization.objects.create(
            name='Scoped Org', org_type='ngo', address='A', city='C', state='S',
            postal_code='1', country='USA', phone='1', email='scoped@example.com',
        )
        Membership.objects.create(
            user=self.user1, organization=organization, role='owner'
        )
        inactive_user = User.objects.create_user(
            username='inactive-reader', password='pass'
        )
        Membership.objects.create(
            user=inactive_user, organization=organization, role='member',
            is_active=False,
        )

        self.client.force_login(self.user1)
        member_detail = self.client.get(
            f'/api/organizations/organizations/{organization.id}/'
        )
        self.assertEqual(member_detail.status_code, status.HTTP_200_OK)

        self.client.force_login(self.user2)
        outsider_detail = self.client.get(
            f'/api/organizations/organizations/{organization.id}/'
        )
        self.assertEqual(outsider_detail.status_code, status.HTTP_404_NOT_FOUND)
        outsider_update = self.client.patch(
            f'/api/organizations/organizations/{organization.id}/',
            data=json.dumps({'name': 'Changed by outsider'}),
            content_type='application/json',
        )
        self.assertEqual(outsider_update.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_login(inactive_user)
        inactive_detail = self.client.get(
            f'/api/organizations/organizations/{organization.id}/'
        )
        self.assertEqual(inactive_detail.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_login(self.admin_user)
        admin_detail = self.client.get(
            f'/api/organizations/organizations/{organization.id}/'
        )
        self.assertEqual(admin_detail.status_code, status.HTTP_200_OK)
        admin_profile_update = self.client.patch(
            f'/api/organizations/organizations/{organization.id}/',
            data=json.dumps({'name': 'Changed by platform admin'}),
            content_type='application/json',
        )
        self.assertEqual(
            admin_profile_update.status_code, status.HTTP_403_FORBIDDEN
        )
        verification = self.client.post(
            f'/api/organizations/organizations/{organization.id}/verify/'
        )
        self.assertEqual(verification.status_code, status.HTTP_200_OK)
        self.assertEqual(verification.json()['status'], 'verified')

    def test_organization_deletion_is_disabled_and_preserves_workflow_records(self):
        organization = Organization.objects.create(
            name='History Org', org_type='restaurant', address='A', city='C',
            state='S', postal_code='1', country='USA', phone='1',
            email='history@example.com', status='verified',
        )
        Membership.objects.create(
            user=self.user1, organization=organization, role='owner'
        )
        Membership.objects.create(
            user=self.user2, organization=organization, role='member'
        )
        recipient = User.objects.create_user(
            username='history-recipient', password='pass', role='recipient'
        )
        recipient_organization = Organization.objects.create(
            name='Recipient Org', org_type='ngo', address='B', city='C',
            state='S', postal_code='2', country='USA', phone='2',
            email='recipient-history@example.com', status='verified',
        )
        Membership.objects.create(
            user=recipient, organization=recipient_organization, role='member'
        )
        now = timezone.now()
        donation = Donation.objects.create(
            donor=self.user1,
            organization=organization,
            title='History donation',
            description='Donation retained with its workflow history',
            food_category='produce',
            quantity=Decimal('5.00'),
            unit='kg',
            available_from=now,
            available_until=now + timedelta(days=1),
            pickup_address='A',
            status='published',
        )
        donation_request = DonationRequest.objects.create(
            recipient=recipient,
            organization=recipient_organization,
            donation=donation,
            requested_quantity=Decimal('2.00'),
            requested_unit='kg',
            status='approved',
        )
        allocation = DonationAllocation.objects.create(
            request=donation_request,
            approved_by=self.user1,
            approved_quantity=Decimal('2.00'),
            approved_unit='kg',
        )
        pickup = Pickup.objects.create(
            donation=donation,
            request=donation_request,
            allocation=allocation,
            pickup_type='self',
            scheduled_at=now + timedelta(hours=1),
            pickup_address='A',
            contact_person='Donor',
            contact_phone='555-0100',
            status='scheduled',
        )

        for deleting_user in (self.user2, self.user1, self.admin_user):
            self.client.force_login(deleting_user)
            response = self.client.delete(
                f'/api/organizations/organizations/{organization.id}/'
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
                response.content,
            )
            self.assertEqual(
                response.json()['detail'],
                'Organization deletion is unavailable to preserve memberships '
                'and donation workflow history.',
            )

        organization.refresh_from_db()
        self.assertEqual(organization.name, 'History Org')
        self.assertEqual(organization.status, 'verified')
        self.assertEqual(
            Membership.objects.filter(organization=organization).count(), 2
        )
        self.assertTrue(Donation.objects.filter(pk=donation.pk).exists())
        self.assertTrue(
            DonationRequest.objects.filter(pk=donation_request.pk).exists()
        )
        self.assertTrue(DonationAllocation.objects.filter(pk=allocation.pk).exists())
        self.assertTrue(Pickup.objects.filter(pk=pickup.pk).exists())
