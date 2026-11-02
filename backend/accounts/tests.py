import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from rest_framework import status


class AuthenticationSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='session-user', password='StrongPass123!', role='recipient'
        )
        self.client = Client(enforce_csrf_checks=True)

    def test_registration_cannot_assign_platform_admin(self):
        response = self.client.post(
            '/api/accounts/register/',
            data=json.dumps({
                'username': 'attempt-admin', 'email': 'attempt@example.test',
                'password': 'StrongPass123!', 'password_confirm': 'StrongPass123!',
                'first_name': 'Attempt', 'last_name': 'Admin', 'phone': '555-0100',
                'role': 'admin',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertFalse(get_user_model().objects.filter(username='attempt-admin').exists())

    def test_registration_requires_explicit_role_and_donor_recipient_can_login(self):
        payload = {
            'email': 'new-account@example.test',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
            'first_name': 'New',
            'last_name': 'Account',
            'phone': '555-0101',
        }
        missing_role = self.client.post(
            '/api/accounts/register/',
            data=json.dumps({'username': 'missing-role', **payload}),
            content_type='application/json',
        )
        self.assertEqual(missing_role.status_code, status.HTTP_400_BAD_REQUEST)

        for role in ('donor', 'recipient'):
            username = f'{role}-account'
            response = self.client.post(
                '/api/accounts/register/',
                data=json.dumps({
                    'username': username,
                    **{**payload, 'email': f'{role}@example.test'},
                    'role': role,
                }),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
            self.assertEqual(response.json()['role'], role)
            self.assertEqual(get_user_model().objects.get(username=username).role, role)

            self.client.get('/api/accounts/csrf_token/')
            token = self.client.cookies['csrftoken'].value
            login_response = self.client.post(
                '/api/accounts/login/',
                data=json.dumps({'username': username, 'password': payload['password']}),
                content_type='application/json', HTTP_X_CSRFTOKEN=token,
                HTTP_ORIGIN='http://localhost:5173',
            )
            self.assertEqual(login_response.status_code, status.HTTP_200_OK, login_response.content)
            self.assertEqual(login_response.json()['role'], role)
            self.assertEqual(self.client.get('/api/accounts/me/').json()['role'], role)

            token = self.client.cookies['csrftoken'].value
            logout_response = self.client.post(
                '/api/accounts/logout/', HTTP_X_CSRFTOKEN=token,
                HTTP_ORIGIN='http://localhost:5173',
            )
            self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

    def test_platform_admin_login_and_session_restore_keep_admin_role(self):
        admin = get_user_model().objects.create_user(
            username='platform-admin', password='StrongPass123!', role='admin'
        )
        self.client.get('/api/accounts/csrf_token/')
        token = self.client.cookies['csrftoken'].value
        login_response = self.client.post(
            '/api/accounts/login/',
            data=json.dumps({
                'username': admin.username,
                'password': 'StrongPass123!',
            }),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN='http://localhost:5173',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK, login_response.content)
        self.assertEqual(login_response.json()['role'], 'admin')
        self.assertEqual(self.client.get('/api/accounts/me/').json()['role'], 'admin')

    def test_login_requires_csrf_and_session_restore_and_logout_work(self):
        payload = json.dumps({'username': 'session-user', 'password': 'StrongPass123!'})
        without_token = self.client.post(
            '/api/accounts/login/', data=payload, content_type='application/json'
        )
        self.assertEqual(without_token.status_code, status.HTTP_403_FORBIDDEN)

        self.client.get('/api/accounts/csrf_token/')
        token = self.client.cookies['csrftoken'].value
        logged_in = self.client.post(
            '/api/accounts/login/', data=payload, content_type='application/json',
            HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='http://localhost:5173',
        )
        self.assertEqual(logged_in.status_code, status.HTTP_200_OK, logged_in.content)
        self.assertEqual(logged_in.json()['role'], 'recipient')

        restored = self.client.get('/api/accounts/me/')
        self.assertEqual(restored.status_code, status.HTTP_200_OK)
        self.assertEqual(restored.json()['username'], 'session-user')

        no_csrf_logout = self.client.post('/api/accounts/logout/', HTTP_ORIGIN='http://localhost:5173')
        self.assertEqual(no_csrf_logout.status_code, status.HTTP_403_FORBIDDEN)
        token = self.client.cookies['csrftoken'].value
        logged_out = self.client.post(
            '/api/accounts/logout/', HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN='http://localhost:5173',
        )
        self.assertEqual(logged_out.status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get('/api/donations/donations/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get('/api/organizations/organizations/').status_code, status.HTTP_403_FORBIDDEN)


class SettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='settings-user', password='StrongPass123!', role='donor',
            email='settings@example.test', first_name='Settings', last_name='User', phone='555-0100',
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.get('/api/accounts/csrf_token/')
        token = self.client.cookies['csrftoken'].value
        self.client.post(
            '/api/accounts/login/',
            data=json.dumps({'username': 'settings-user', 'password': 'StrongPass123!'}),
            content_type='application/json', HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN='http://localhost:5173',
        )

    def _csrf_token(self):
        self.client.get('/api/accounts/csrf_token/')
        return self.client.cookies['csrftoken'].value

    def _patch_me(self, payload):
        return self.client.patch(
            '/api/accounts/me/',
            data=json.dumps(payload),
            content_type='application/json', HTTP_X_CSRFTOKEN=self._csrf_token(),
            HTTP_ORIGIN='http://localhost:5173',
        )

    def _post_change_password(self, payload):
        return self.client.post(
            '/api/accounts/change-password/',
            data=json.dumps(payload),
            content_type='application/json', HTTP_X_CSRFTOKEN=self._csrf_token(),
            HTTP_ORIGIN='http://localhost:5173',
        )

    def test_authenticated_user_can_update_own_profile_fields(self):
        response = self._patch_me({
            'first_name': 'Updated', 'last_name': 'Name', 'phone': '555-0200',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(self.user.phone, '555-0200')
        self.assertEqual(response.json()['first_name'], 'Updated')
        self.assertEqual(response.json()['last_name'], 'Name')
        self.assertEqual(response.json()['phone'], '555-0200')

    def test_profile_update_rejects_invalid_email(self):
        response = self._patch_me({'email': 'not-an-email'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'settings@example.test')

    def test_profile_update_cannot_change_role(self):
        response = self._patch_me({'role': 'admin'})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, 'donor')

    def test_profile_update_cannot_change_is_verified(self):
        response = self._patch_me({'is_verified': True})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)

    def test_profile_update_requires_authentication(self):
        self.client.logout()
        response = self._patch_me({'first_name': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.content)

    def test_password_change_success(self):
        response = self._post_change_password({
            'current_password': 'StrongPass123!',
            'new_password': 'NewStrongPass123!',
            'new_password_confirm': 'NewStrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()['detail'], 'Password changed successfully.')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStrongPass123!'))

    def test_password_change_rejects_wrong_current_password(self):
        response = self._post_change_password({
            'current_password': 'WrongPassword!',
            'new_password': 'NewStrongPass123!',
            'new_password_confirm': 'NewStrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertIn('current_password', response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('StrongPass123!'))

    def test_password_change_rejects_same_password(self):
        response = self._post_change_password({
            'current_password': 'StrongPass123!',
            'new_password': 'StrongPass123!',
            'new_password_confirm': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_password_change_requires_authentication(self):
        self.client.logout()
        response = self._post_change_password({
            'current_password': 'StrongPass123!',
            'new_password': 'NewStrongPass123!',
            'new_password_confirm': 'NewStrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.content)

    def test_password_change_session_remains_valid(self):
        response = self._post_change_password({
            'current_password': 'StrongPass123!',
            'new_password': 'NewStrongPass123!',
            'new_password_confirm': 'NewStrongPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        # Session should still be valid after password change
        me_response = self.client.get('/api/accounts/me/')
        self.assertEqual(me_response.status_code, status.HTTP_200_OK, me_response.content)
        # Old password should no longer work
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStrongPass123!'))
        self.assertFalse(self.user.check_password('StrongPass123!'))
