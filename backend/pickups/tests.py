from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from donations.models import Donation
from donation_requests.models import DonationAllocation, DonationRequest
from organizations.models import Membership, Organization
from .models import Pickup


class VolunteerPickupDiscoveryClaimTests(APITestCase):
    def setUp(self):
        self.donor = User.objects.create_user(username='disc-donor', password='pass', role='donor')
        self.recipient = User.objects.create_user(username='disc-recipient', password='pass', role='recipient')
        self.volunteer = User.objects.create_user(username='disc-volunteer', password='pass', role='volunteer')
        self.other_volunteer = User.objects.create_user(username='disc-other-volunteer', password='pass', role='volunteer')
        self.donor_org = Organization.objects.create(
            name='Disc Donor Org', org_type='restaurant', address='1 Road', city='City',
            state='State', postal_code='10000', country='USA', phone='555-0200',
            email='disc-donor@example.test', status='verified',
        )
        self.recipient_org = Organization.objects.create(
            name='Disc Recipient Org', org_type='ngo', address='2 Road', city='City',
            state='State', postal_code='10000', country='USA', phone='555-0201',
            email='disc-recipient@example.test', status='verified',
        )
        self.other_org = Organization.objects.create(
            name='Disc Other Org', org_type='restaurant', address='3 Road', city='City',
            state='State', postal_code='10000', country='USA', phone='555-0202',
            email='disc-other@example.test', status='verified',
        )
        Membership.objects.create(user=self.donor, organization=self.donor_org, role='owner')
        Membership.objects.create(user=self.recipient, organization=self.recipient_org, role='member')
        Membership.objects.create(user=self.volunteer, organization=self.recipient_org, role='volunteer')
        Membership.objects.create(user=self.other_volunteer, organization=self.other_org, role='volunteer')

        now = timezone.now()
        donation = Donation.objects.create(
            donor=self.donor, organization=self.donor_org, title='Disc food',
            description='desc', food_category='produce', quantity=Decimal('10.00'),
            unit='kg', available_from=now - timedelta(days=1),
            available_until=now + timedelta(days=2), pickup_address='1 Road',
            status='reserved',
        )
        request_obj = DonationRequest.objects.create(
            recipient=self.recipient, organization=self.recipient_org, donation=donation,
            requested_quantity=Decimal('5'), requested_unit='kg', status='approved',
        )
        allocation = DonationAllocation.objects.create(
            request=request_obj, approved_by=self.donor,
            approved_quantity=Decimal('5'), approved_unit='kg',
        )
        self.claimable_pickup = Pickup.objects.create(
            donation=donation, request=request_obj, allocation=allocation,
            pickup_type='self', scheduled_at=now + timedelta(hours=2),
            pickup_address='1 Road', contact_person='Donor', contact_phone='555-0200',
            status='scheduled',
        )
        self.volunteer_client = APIClient()
        self.volunteer_client.force_authenticate(self.volunteer)
        self.other_volunteer_client = APIClient()
        self.other_volunteer_client.force_authenticate(self.other_volunteer)
        self.donor_client = APIClient()
        self.donor_client.force_authenticate(self.donor)
        self.anon_client = APIClient()

    def test_eligible_volunteer_discovers_claimable_pickup(self):
        response = self.volunteer_client.get('/api/pickups/claimable/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data.get('results', response.data)]
        self.assertIn(self.claimable_pickup.pk, ids)

    def test_ineligible_volunteer_cannot_discover_pickup(self):
        response = self.other_volunteer_client.get('/api/pickups/claimable/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data.get('results', response.data)]
        self.assertNotIn(self.claimable_pickup.pk, ids)

    def test_assigned_pickup_excluded_from_discovery(self):
        self.claimable_pickup.volunteer = self.volunteer
        self.claimable_pickup.save(update_fields=['volunteer'])
        response = self.volunteer_client.get('/api/pickups/claimable/')
        ids = [item['id'] for item in response.data.get('results', response.data)]
        self.assertNotIn(self.claimable_pickup.pk, ids)

    def test_nonscheduled_pickup_excluded_from_discovery(self):
        self.claimable_pickup.status = 'completed'
        self.claimable_pickup.actual_quantity = Decimal('5.00')
        self.claimable_pickup.actual_unit = 'kg'
        self.claimable_pickup.started_at = timezone.now()
        self.claimable_pickup.completed_at = timezone.now()
        self.claimable_pickup.save(update_fields=['status', 'actual_quantity', 'actual_unit', 'started_at', 'completed_at'])
        response = self.volunteer_client.get('/api/pickups/claimable/')
        ids = [item['id'] for item in response.data.get('results', response.data)]
        self.assertNotIn(self.claimable_pickup.pk, ids)

    def test_eligible_volunteer_can_claim(self):
        response = self.volunteer_client.post(f'/api/pickups/{self.claimable_pickup.pk}/claim/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.claimable_pickup.refresh_from_db()
        self.assertEqual(self.claimable_pickup.volunteer_id, self.volunteer.pk)

    def test_ineligible_volunteer_cannot_claim(self):
        response = self.other_volunteer_client.post(f'/api/pickups/{self.claimable_pickup.pk}/claim/')
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        self.claimable_pickup.refresh_from_db()
        self.assertIsNone(self.claimable_pickup.volunteer_id)

    def test_donor_cannot_claim(self):
        response = self.donor_client.post(f'/api/pickups/{self.claimable_pickup.pk}/claim/')
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_unauthenticated_claim_rejected(self):
        response = self.anon_client.post(f'/api/pickups/{self.claimable_pickup.pk}/claim/')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_second_claim_does_not_overwrite(self):
        first = self.volunteer_client.post(f'/api/pickups/{self.claimable_pickup.pk}/claim/')
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        second = self.other_volunteer_client.post(f'/api/pickups/{self.claimable_pickup.pk}/claim/')
        self.assertNotEqual(second.status_code, status.HTTP_200_OK)
        self.claimable_pickup.refresh_from_db()
        self.assertEqual(self.claimable_pickup.volunteer_id, self.volunteer.pk)
class PickupWorkflowTests(APITestCase):
    def setUp(self):
        self.donor = User.objects.create_user(
            username='pickup-donor', password='pass', role='donor', phone='555-0100'
        )
        self.recipient = User.objects.create_user(
            username='pickup-recipient', password='pass', role='recipient'
        )
        self.outsider = User.objects.create_user(
            username='pickup-outsider', password='pass', role='donor'
        )
        self.volunteer = User.objects.create_user(
            username='pickup-volunteer', password='pass', role='volunteer'
        )
        self.unrelated_volunteer = User.objects.create_user(
            username='unrelated-volunteer', password='pass', role='volunteer'
        )
        self.donor_org = self.make_organization('Donor Org', 'restaurant')
        self.recipient_org = self.make_organization('Recipient Org', 'ngo')
        self.outsider_org = self.make_organization('Outsider Org', 'restaurant')
        Membership.objects.create(
            user=self.donor, organization=self.donor_org, role='owner'
        )
        Membership.objects.create(
            user=self.recipient, organization=self.recipient_org, role='member'
        )
        Membership.objects.create(
            user=self.outsider, organization=self.outsider_org, role='owner'
        )
        Membership.objects.create(
            user=self.volunteer, organization=self.recipient_org, role='volunteer'
        )

        now = timezone.now()
        self.donation = Donation.objects.create(
            donor=self.donor,
            organization=self.donor_org,
            title='Pickup produce',
            description='Food for pickup tests',
            food_category='produce',
            quantity=Decimal('25.00'),
            unit='kg',
            available_from=now - timedelta(days=1),
            available_until=now + timedelta(days=2),
            pickup_address='10 Donor Road',
            status='reserved',
        )
        self.request = self.make_request()
        self.allocation = self.make_allocation(self.request)

        self.donor_client = APIClient()
        self.donor_client.force_authenticate(self.donor)
        self.recipient_client = APIClient()
        self.recipient_client.force_authenticate(self.recipient)
        self.outsider_client = APIClient()
        self.outsider_client.force_authenticate(self.outsider)
        self.volunteer_client = APIClient()
        self.volunteer_client.force_authenticate(self.volunteer)

    def make_organization(self, name, org_type):
        return Organization.objects.create(
            name=name,
            org_type=org_type,
            address='1 Test Road',
            city='Test City',
            state='Test State',
            postal_code='10000',
            country='USA',
            phone='555-0101',
            email=f'{name.lower().replace(" ", "-")}@example.test',
            status='verified',
        )

    def make_request(self, *, status='approved', unit='kg', quantity='8'):
        return DonationRequest.objects.create(
            recipient=self.recipient,
            organization=self.recipient_org,
            donation=self.donation,
            requested_quantity=Decimal(quantity),
            requested_unit=unit,
            status=status,
        )

    def make_allocation(self, request_obj, *, quantity='5', unit=None):
        return DonationAllocation.objects.create(
            request=request_obj,
            approved_by=self.donor,
            approved_quantity=Decimal(quantity),
            approved_unit=unit or request_obj.requested_unit,
        )

    def schedule_payload(self, allocation=None, **overrides):
        payload = {
            'allocation': (allocation or self.allocation).pk,
            'pickup_type': 'self',
            'scheduled_at': (timezone.now() + timedelta(hours=2)).isoformat(),
            'pickup_address': self.donation.pickup_address,
            'contact_person': 'Donor Org',
            'contact_phone': '555-0100',
            'notes': 'Use the side entrance',
        }
        payload.update(overrides)
        return payload

    def schedule(self, client=None, allocation=None, **overrides):
        return (client or self.donor_client).post(
            '/api/pickups/',
            self.schedule_payload(allocation, **overrides),
            format='json',
        )

    def make_pickup(self, *, client=None, allocation=None):
        response = self.schedule(client, allocation)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return Pickup.objects.get(pk=response.data['id'])

    def test_donor_or_recipient_member_can_schedule_exactly_one_pickup(
        self
    ):
        created = self.schedule(client=self.recipient_client)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(created.data['allocation'], self.allocation.pk)
        self.assertEqual(created.data['donation'], self.donation.pk)
        self.assertEqual(created.data['request'], self.request.pk)
        self.assertEqual(created.data['status'], 'scheduled')
        self.assertEqual(Pickup.objects.count(), 1)

        duplicate = self.schedule(client=self.donor_client)
        self.assertEqual(duplicate.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Pickup.objects.count(), 1)

    def test_any_active_organization_member_can_schedule_and_list(self):
        donor_member = User.objects.create_user(
            username='pickup-donor-member', password='pass', role='donor'
        )
        Membership.objects.create(
            user=donor_member, organization=self.donor_org, role='member'
        )
        client = APIClient()
        client.force_authenticate(donor_member)
        pickup_response = self.schedule(client=client)
        self.assertEqual(pickup_response.status_code, status.HTTP_201_CREATED)
        listed = client.get('/api/pickups/')
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data['count'], 1)

    def test_database_unique_constraint_prevents_duplicate_allocation_pickups(self):
        pickup = self.make_pickup()
        duplicate = Pickup(
            donation=pickup.donation,
            request=pickup.request,
            allocation=pickup.allocation,
            pickup_type=pickup.pickup_type,
            scheduled_at=pickup.scheduled_at + timedelta(hours=1),
            pickup_address=pickup.pickup_address,
            contact_person=pickup.contact_person,
            contact_phone=pickup.contact_phone,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Pickup.objects.bulk_create([duplicate])
        self.assertEqual(Pickup.objects.filter(allocation=self.allocation).count(), 1)

    def test_request_and_donation_ids_cannot_override_allocation_relationships(self):
        payload = self.schedule_payload()
        payload['request'] = 9999
        payload['donation'] = 9999
        created = self.donor_client.post('/api/pickups/', payload, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        pickup = Pickup.objects.get(pk=created.data['id'])
        self.assertEqual(pickup.request_id, self.request.pk)
        self.assertEqual(pickup.donation_id, self.donation.pk)

    def test_status_and_relationships_are_not_mutable_through_patch(self):
        pickup = self.make_pickup()
        response = self.donor_client.patch(
            f'/api/pickups/{pickup.pk}/',
            {
                'status': 'completed',
                'allocation': 99999,
                'donation': 99999,
                'request': 99999,
                'volunteer': self.unrelated_volunteer.pk,
                'actual_quantity': '999',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        pickup.refresh_from_db()
        self.assertEqual(pickup.status, 'scheduled')
        self.assertEqual(pickup.allocation_id, self.allocation.pk)
        self.assertEqual(pickup.donation_id, self.donation.pk)
        self.assertIsNone(pickup.volunteer_id)
        self.assertIsNone(pickup.actual_quantity)

    def test_invalid_schedule_time_and_type_are_rejected(self):
        invalid_time = self.schedule(
            scheduled_at=(timezone.now() - timedelta(minutes=1)).isoformat()
        )
        self.assertEqual(invalid_time.status_code, status.HTTP_400_BAD_REQUEST)
        invalid_type = self.schedule(pickup_type='unrecognized')
        self.assertEqual(invalid_type.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Pickup.objects.count(), 0)

    def test_pending_or_rejected_requests_cannot_have_pickups(self):
        pending = self.make_request(status='pending')
        pending_allocation = self.make_allocation(pending)
        response = self.schedule(allocation=pending_allocation)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Pickup.objects.count(), 0)

        rejected = self.make_request(status='rejected')
        rejected_allocation = self.make_allocation(rejected)
        response = self.schedule(allocation=rejected_allocation)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Pickup.objects.count(), 0)

    def test_unrelated_users_cannot_list_retrieve_or_schedule(self):
        pickup = self.make_pickup()
        self.assertEqual(self.outsider_client.get('/api/pickups/').data['count'], 0)
        self.assertEqual(
            self.outsider_client.get(f'/api/pickups/{pickup.pk}/').status_code,
            status.HTTP_404_NOT_FOUND,
        )
        allocation = self.make_allocation(self.make_request())
        denied = self.schedule(self.outsider_client, allocation)
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)
        anonymous = APIClient()
        self.assertEqual(anonymous.get('/api/pickups/').status_code, status.HTTP_403_FORBIDDEN)

    def test_assigned_volunteer_can_access_and_progress_only_assigned_pickup(self):
        pickup = self.make_pickup()
        assigned = self.donor_client.post(
            f'/api/pickups/{pickup.pk}/assign-volunteer/',
            {'volunteer': self.volunteer.pk},
            format='json',
        )
        self.assertEqual(assigned.status_code, status.HTTP_200_OK, assigned.data)
        pickup.refresh_from_db()

        self.assertEqual(self.volunteer_client.get('/api/pickups/').data['count'], 1)
        pickup.scheduled_at = timezone.now() - timedelta(minutes=1)
        pickup.save(update_fields=['scheduled_at', 'updated_at'])
        started = self.volunteer_client.post(
            f'/api/pickups/{pickup.pk}/start/', {}, format='json'
        )
        self.assertEqual(started.status_code, status.HTTP_200_OK, started.data)
        self.assertEqual(started.data['status'], 'in_progress')
        self.assertIsNotNone(started.data['started_at'])

        completed = self.volunteer_client.post(
            f'/api/pickups/{pickup.pk}/complete/',
            {'actual_quantity': '4.250', 'actual_unit': 'kg'},
            format='json',
        )
        self.assertEqual(completed.status_code, status.HTTP_200_OK, completed.data)
        self.assertEqual(completed.data['actual_quantity'], '4.250')
        self.assertEqual(completed.data['actual_unit'], 'kg')
        self.assertEqual(completed.data['status'], 'completed')
        self.assertIsNotNone(completed.data['completed_at'])

        self.assertEqual(
            self.volunteer_client.post(
                f'/api/pickups/{pickup.pk}/start/', {}, format='json'
            ).status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            self.volunteer_client.post(
                f'/api/pickups/{pickup.pk}/cancel/', {}, format='json'
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_ineligible_volunteer_assignment_is_rejected_and_removable(self):
        pickup = self.make_pickup()
        denied = self.donor_client.post(
            f'/api/pickups/{pickup.pk}/assign-volunteer/',
            {'volunteer': self.unrelated_volunteer.pk},
            format='json',
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)
        pickup.refresh_from_db()
        self.assertIsNone(pickup.volunteer_id)

        assigned = self.recipient_client.post(
            f'/api/pickups/{pickup.pk}/assign-volunteer/',
            {'volunteer': self.volunteer.pk},
            format='json',
        )
        self.assertEqual(assigned.status_code, status.HTTP_200_OK)
        removed = self.donor_client.post(
            f'/api/pickups/{pickup.pk}/assign-volunteer/',
            {'volunteer': None},
            format='json',
        )
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        pickup.refresh_from_db()
        self.assertIsNone(pickup.volunteer_id)
        self.assertEqual(self.volunteer_client.get('/api/pickups/').data['count'], 0)

    def test_completion_validates_quantity_unit_and_does_not_change_allocation(self):
        pickup = self.make_pickup()
        pickup.scheduled_at = timezone.now() - timedelta(minutes=1)
        pickup.save(update_fields=['scheduled_at', 'updated_at'])
        self.donor_client.post(f'/api/pickups/{pickup.pk}/start/', {}, format='json')
        allocation_count = DonationAllocation.objects.count()

        too_much = self.donor_client.post(
            f'/api/pickups/{pickup.pk}/complete/',
            {'actual_quantity': '5.001', 'actual_unit': 'kg'},
            format='json',
        )
        self.assertEqual(too_much.status_code, status.HTTP_400_BAD_REQUEST)
        incompatible = self.donor_client.post(
            f'/api/pickups/{pickup.pk}/complete/',
            {'actual_quantity': '1', 'actual_unit': 'l'},
            format='json',
        )
        self.assertEqual(incompatible.status_code, status.HTTP_400_BAD_REQUEST)
        pickup.refresh_from_db()
        self.assertEqual(pickup.status, 'in_progress')
        self.assertIsNone(pickup.actual_quantity)
        self.assertEqual(DonationAllocation.objects.count(), allocation_count)

        partial = self.donor_client.post(
            f'/api/pickups/{pickup.pk}/complete/',
            {'actual_quantity': '500', 'actual_unit': 'g'},
            format='json',
        )
        self.assertEqual(partial.status_code, status.HTTP_200_OK, partial.data)
        self.assertEqual(partial.data['actual_quantity'], '500.000')
        self.assertEqual(partial.data['actual_unit'], 'g')
        self.assertEqual(DonationAllocation.objects.count(), allocation_count)
        self.assertEqual(
            self.donor_client.post(
                f'/api/pickups/{pickup.pk}/cancel/', {}, format='json'
            ).status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_in_progress_failure_requires_reason_and_does_not_consume_allocation(self):
        pickup = self.make_pickup()
        assigned = self.donor_client.post(
            f'/api/pickups/{pickup.pk}/assign-volunteer/',
            {'volunteer': self.volunteer.pk},
            format='json',
        )
        self.assertEqual(assigned.status_code, status.HTTP_200_OK, assigned.data)
        pickup.scheduled_at = timezone.now() - timedelta(minutes=1)
        pickup.save(update_fields=['scheduled_at', 'updated_at'])
        self.assertEqual(
            self.donor_client.post(
                f'/api/pickups/{pickup.pk}/start/', {}, format='json'
            ).status_code,
            status.HTTP_200_OK,
        )
        allocation_count = DonationAllocation.objects.count()
        missing_reason = self.donor_client.post(
            f'/api/pickups/{pickup.pk}/fail/', {}, format='json'
        )
        self.assertEqual(missing_reason.status_code, status.HTTP_400_BAD_REQUEST)

        failed = self.volunteer_client.post(
            f'/api/pickups/{pickup.pk}/fail/',
            {'failure_reason': 'Packaging was damaged'},
            format='json',
        )
        self.assertEqual(failed.status_code, status.HTTP_200_OK, failed.data)
        self.assertEqual(failed.data['status'], 'failed')
        self.assertEqual(failed.data['failure_reason'], 'Packaging was damaged')
        self.assertIsNotNone(failed.data['failed_at'])
        self.assertIsNone(failed.data['actual_quantity'])
        self.assertEqual(DonationAllocation.objects.count(), allocation_count)
        self.assertEqual(
            self.donor_client.post(
                f'/api/pickups/{pickup.pk}/complete/',
                {'actual_quantity': '1', 'actual_unit': 'kg'},
                format='json',
            ).status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_count_and_volume_allocations_keep_their_units(self):
        for unit in ('units', 'l'):
            donation = Donation.objects.create(
                donor=self.donor,
                organization=self.donor_org,
                title=f'{unit} donation',
                description='Unit-preservation check',
                food_category='other',
                quantity=Decimal('10'),
                unit=unit,
                available_from=timezone.now() - timedelta(days=1),
                available_until=timezone.now() + timedelta(days=1),
                pickup_address='10 Donor Road',
                status='reserved',
            )
            request_obj = DonationRequest.objects.create(
                recipient=self.recipient,
                organization=self.recipient_org,
                donation=donation,
                requested_quantity=Decimal('5'),
                requested_unit=unit,
                status='approved',
            )
            allocation = self.make_allocation(request_obj, quantity='3', unit=unit)
            response = self.schedule(
                self.recipient_client,
                allocation,
                **{'pickup_address': donation.pickup_address},
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
            pickup = Pickup.objects.get(pk=response.data['id'])
            pickup.scheduled_at = timezone.now() - timedelta(minutes=1)
            pickup.save(update_fields=['scheduled_at', 'updated_at'])
            started = self.recipient_client.post(
                f'/api/pickups/{pickup.pk}/start/', {}, format='json'
            )
            self.assertEqual(started.status_code, status.HTTP_200_OK)
            completed = self.recipient_client.post(
                f'/api/pickups/{pickup.pk}/complete/',
                {'actual_quantity': '2', 'actual_unit': unit},
                format='json',
            )
            self.assertEqual(completed.status_code, status.HTTP_200_OK, completed.data)
            self.assertEqual(completed.data['actual_unit'], unit)
            self.assertIsNone(Pickup.objects.get(pk=pickup.pk).actual_quantity_kg)

    def test_cancel_no_show_and_reschedule_rules(self):
        pickup = self.make_pickup()
        invalid_reschedule = self.donor_client.patch(
            f'/api/pickups/{pickup.pk}/',
            {'scheduled_at': (timezone.now() - timedelta(minutes=1)).isoformat()},
            format='json',
        )
        self.assertEqual(invalid_reschedule.status_code, status.HTTP_400_BAD_REQUEST)
        pickup.refresh_from_db()
        self.assertEqual(pickup.status, 'scheduled')

        rescheduled = self.recipient_client.patch(
            f'/api/pickups/{pickup.pk}/',
            {'scheduled_at': (timezone.now() + timedelta(days=1)).isoformat()},
            format='json',
        )
        self.assertEqual(rescheduled.status_code, status.HTTP_200_OK)

        too_early_start = self.donor_client.post(
            f'/api/pickups/{pickup.pk}/start/', {}, format='json'
        )
        self.assertEqual(too_early_start.status_code, status.HTTP_400_BAD_REQUEST)
        too_early = self.donor_client.post(
            f'/api/pickups/{pickup.pk}/no-show/', {}, format='json'
        )
        self.assertEqual(too_early.status_code, status.HTTP_400_BAD_REQUEST)
        cancelled = self.recipient_client.post(
            f'/api/pickups/{pickup.pk}/cancel/', {}, format='json'
        )
        self.assertEqual(cancelled.status_code, status.HTTP_200_OK)
        self.assertEqual(cancelled.data['status'], 'cancelled')
        self.assertIsNotNone(cancelled.data['cancelled_at'])
        self.assertEqual(
            self.donor_client.post(
                f'/api/pickups/{pickup.pk}/start/', {}, format='json'
            ).status_code,
            status.HTTP_409_CONFLICT,
        )

        allocation = self.make_allocation(self.make_request())
        missed = self.make_pickup(allocation=allocation)
        missed.scheduled_at = timezone.now() - timedelta(minutes=1)
        missed.save(update_fields=['scheduled_at', 'updated_at'])
        no_show = self.volunteer_client.post(
            f'/api/pickups/{missed.pk}/no-show/', {}, format='json'
        )
        self.assertEqual(no_show.status_code, status.HTTP_404_NOT_FOUND)
        assigned = self.donor_client.post(
            f'/api/pickups/{missed.pk}/assign-volunteer/',
            {'volunteer': self.volunteer.pk},
            format='json',
        )
        self.assertEqual(assigned.status_code, status.HTTP_200_OK)
        no_show = self.volunteer_client.post(
            f'/api/pickups/{missed.pk}/no-show/', {}, format='json'
        )
        self.assertEqual(no_show.status_code, status.HTTP_200_OK, no_show.data)
        self.assertEqual(no_show.data['status'], 'no_show')
        self.assertIsNotNone(no_show.data['no_show_at'])

    def test_model_rejects_mismatched_allocation_links(self):
        other_donation = Donation.objects.create(
            donor=self.donor,
            organization=self.donor_org,
            title='Different donation',
            description='Mismatch test',
            food_category='other',
            quantity=Decimal('5'),
            unit='kg',
            available_from=timezone.now() - timedelta(days=1),
            available_until=timezone.now() + timedelta(days=1),
            pickup_address='Other address',
            status='reserved',
        )
        pickup = Pickup(
            donation=other_donation,
            request=self.request,
            allocation=self.allocation,
            pickup_type='self',
            scheduled_at=timezone.now() + timedelta(hours=1),
            pickup_address=other_donation.pickup_address,
            contact_person='Contact',
            contact_phone='555-0100',
        )
        with self.assertRaises(DjangoValidationError):
            pickup.save()


@skipUnless(
    connection.features.has_select_for_update,
    'Concurrent pickup scheduling requires a database with row-lock support (for example PostgreSQL).',
)
class ConcurrentPickupSchedulingTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        now = timezone.now()
        self.donor = User.objects.create_user(
            username='concurrent-pickup-donor', password='pass', role='donor'
        )
        self.recipient = User.objects.create_user(
            username='concurrent-pickup-recipient', password='pass', role='recipient'
        )
        self.donor_org = Organization.objects.create(
            name='Concurrent pickup donor',
            org_type='restaurant',
            address='1 Test Road',
            city='Test City',
            state='Test State',
            postal_code='10000',
            phone='555-0110',
            email='concurrent-pickup-donor@example.test',
            status='verified',
        )
        self.recipient_org = Organization.objects.create(
            name='Concurrent pickup recipient',
            org_type='ngo',
            address='2 Test Road',
            city='Test City',
            state='Test State',
            postal_code='10001',
            phone='555-0111',
            email='concurrent-pickup-recipient@example.test',
            status='verified',
        )
        Membership.objects.create(
            user=self.donor, organization=self.donor_org, role='owner'
        )
        Membership.objects.create(
            user=self.recipient, organization=self.recipient_org, role='member'
        )
        donation = Donation.objects.create(
            donor=self.donor,
            organization=self.donor_org,
            title='Concurrent pickup food',
            description='Concurrent pickup test',
            food_category='produce',
            quantity=Decimal('10'),
            unit='kg',
            available_from=now - timedelta(hours=1),
            available_until=now + timedelta(days=1),
            pickup_address='1 Test Road',
            status='reserved',
        )
        request_obj = DonationRequest.objects.create(
            recipient=self.recipient,
            organization=self.recipient_org,
            donation=donation,
            requested_quantity=Decimal('5'),
            requested_unit='kg',
            status='approved',
        )
        self.allocation = DonationAllocation.objects.create(
            request=request_obj,
            approved_by=self.donor,
            approved_quantity=Decimal('5'),
            approved_unit='kg',
        )

    def test_two_concurrent_schedule_attempts_create_one_pickup(self):
        barrier = Barrier(2)
        allocation_id = self.allocation.pk
        donor_id = self.donor.pk

        def schedule():
            close_old_connections()
            try:
                actor = User.objects.get(pk=donor_id)
                client = APIClient()
                client.force_authenticate(actor)
                barrier.wait(timeout=5)
                response = client.post(
                    '/api/pickups/',
                    {
                        'allocation': allocation_id,
                        'pickup_type': 'self',
                        'scheduled_at': (timezone.now() + timedelta(hours=1)).isoformat(),
                        'pickup_address': '1 Test Road',
                        'contact_person': 'Donor',
                        'contact_phone': '555-0110',
                    },
                    format='json',
                )
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: schedule(), range(2)))

        self.assertCountEqual(results, [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT])
        self.assertEqual(Pickup.objects.filter(allocation_id=allocation_id).count(), 1)
