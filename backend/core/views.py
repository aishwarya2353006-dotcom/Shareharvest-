from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db import connection


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_status = 'ok'
        try:
            connection.ensure_connection()
        except Exception:
            db_status = 'unavailable'

        return Response({
            'service': 'ShareHarvest API',
            'status': 'ok',
            'database': db_status,
        })