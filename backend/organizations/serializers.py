from rest_framework import serializers

from .models import Organization, Membership
from accounts.models import User

class MembershipUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'role']



class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"
        read_only_fields = ["verified_at", "verified_by", "status", "created_at", "updated_at"]

class MembershipSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    organization = serializers.PrimaryKeyRelatedField(queryset=Organization.objects.all())
    user_details = MembershipUserSerializer(source="user", read_only=True)


    class Meta:
        model = Membership
        fields = ["id", "user", "user_details", "organization", "role", "joined_at", "is_active"]
        read_only_fields = ["joined_at"]
        # The custom validation below provides an actionable message for
        # inactive memberships, which still occupy the model's unique pair.
        validators = []

    def validate(self, attrs):
        user = attrs.get("user", getattr(self.instance, "user", None))
        organization = attrs.get("organization", getattr(self.instance, "organization", None))
        existing = Membership.objects.filter(user=user, organization=organization)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.filter(is_active=True).exists():
            raise serializers.ValidationError("User already has an active membership in this organization.")
        if self.instance is None and existing.exists():
            raise serializers.ValidationError(
                "An inactive membership already exists. Reactivate that membership instead."
            )
        return attrs
