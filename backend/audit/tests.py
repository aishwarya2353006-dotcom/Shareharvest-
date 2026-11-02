from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from audit.models import AuditLog
from audit.services import log_audit
from rest_framework import status

User = get_user_model()

class AuditLogTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(username='admin', password='pass', role='admin')
        self.non_admin_user = User.objects.create_user(username='user1', password='pass', role='donor')

    def test_audit_log_creation_via_service(self):
        log = log_audit(
            user=self.admin_user,
            action='create',
            object_type='Donation',
            object_id=1,
            object_repr='Test Donation',
            changes={'status': 'published'},
        )
        self.assertEqual(AuditLog.objects.count(), 1)
        audit = AuditLog.objects.first()
        self.assertEqual(audit.user, self.admin_user)
        self.assertEqual(audit.action, 'create')
        self.assertEqual(audit.object_type, 'Donation')
        self.assertEqual(audit.object_id, 1)
        self.assertEqual(audit.object_repr, 'Test Donation')
        self.assertEqual(audit.changes, {'status': 'published'})

    def test_audit_log_with_request_captures_ip_and_user_agent(self):
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
        log_audit(
            user=self.admin_user,
            action='update',
            object_type='Organization',
            object_id=2,
            request=request,
        )
        audit = AuditLog.objects.first()
        self.assertEqual(audit.ip_address, '127.0.0.1')
        self.assertEqual(audit.user_agent, 'TestAgent/1.0')

    def test_non_admin_cannot_list_audit_logs(self):
        log_audit(user=self.admin_user, action='create', object_type='Donation', object_id=1)
        self.client.force_login(self.non_admin_user)
        response = self.client.get('/api/audit/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_audit_logs(self):
        log_audit(user=self.admin_user, action='create', object_type='Donation', object_id=1)
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/audit/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)

    def test_admin_can_filter_audit_logs_by_object_type(self):
        log_audit(user=self.admin_user, action='create', object_type='Donation', object_id=1)
        log_audit(user=self.admin_user, action='update', object_type='Organization', object_id=2)
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/audit/?object_type=Donation')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['object_type'], 'Donation')

    def test_admin_can_filter_audit_logs_by_action(self):
        log_audit(user=self.admin_user, action='create', object_type='Donation', object_id=1)
        log_audit(user=self.admin_user, action='update', object_type='Donation', object_id=2)
        self.client.force_login(self.admin_user)
        response = self.client.get('/api/audit/?action=update')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['action'], 'update')

    def test_audit_log_readonly_no_create_endpoint(self):
        self.client.force_login(self.admin_user)
        response = self.client.post('/api/audit/', {
            'action': 'create',
            'object_type': 'Donation',
            'object_id': 1,
        }, format='json')
        self.assertIn(response.status_code, [status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_audit_log_detail_requires_admin(self):
        audit = AuditLog.objects.create(user=self.admin_user, action='create', object_type='Donation', object_id=1)
        self.client.force_login(self.non_admin_user)
        response = self.client.get(f'/api/audit/{audit.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_audit_log_detail_admin_can_view(self):
        audit = AuditLog.objects.create(user=self.admin_user, action='create', object_type='Donation', object_id=1)
        self.client.force_login(self.admin_user)
        response = self.client.get(f'/api/audit/{audit.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['action'], 'create')
        self.assertEqual(data['object_type'], 'Donation')
