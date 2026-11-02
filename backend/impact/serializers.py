from rest_framework import serializers

from .models import ImpactReport


class ImpactReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImpactReport
        fields = '__all__'
