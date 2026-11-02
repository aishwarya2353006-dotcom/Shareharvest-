from django.test import TestCase, Client
from rest_framework import status

class HealthCheckTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_endpoint_responds(self):
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_response_fields(self):
        response = self.client.get('/api/health/')
        data = response.json()
        self.assertIn('service', data)
        self.assertIn('status', data)
        self.assertIn('database', data)
        self.assertEqual(data['service'], 'ShareHarvest API')
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['database'], 'ok')

    def test_health_response_types(self):
        response = self.client.get('/api/health/')
        data = response.json()
        self.assertIsInstance(data['service'], str)
        self.assertIsInstance(data['status'], str)
        self.assertIsInstance(data['database'], str)

    def test_health_no_sensitive_data(self):
        response = self.client.get('/api/health/')
        data = response.json()
        sensitive_keys = ['secret_key', 'password', 'token', 'api_key', 'env', 'debug']
        for key in sensitive_keys:
            self.assertNotIn(key, data)
        # Ensure no value looks like a secret
        for value in data.values():
            if isinstance(value, str):
                self.assertNotIn('django-insecure', value)
                self.assertNotIn('SECRET', value)

    def test_health_public_access(self):
        # No authentication required
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_database_status_ok(self):
        response = self.client.get('/api/health/')
        data = response.json()
        self.assertEqual(data['database'], 'ok')
