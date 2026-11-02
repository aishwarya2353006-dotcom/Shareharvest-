from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from .models import Organization, Membership
from .serializers import OrganizationSerializer, MembershipSerializer
from accounts.models import User
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from audit.services import log_audit


class IsOrganizationMemberOrPlatformAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        memberships = Membership.objects.filter(
            user=request.user, organization=obj, is_active=True
        )
        if request.method in permissions.SAFE_METHODS:
            return request.user.role == "admin" or memberships.exists()
        if view.action in ("update", "partial_update"):
            return memberships.filter(role__in=("owner", "admin")).exists()
        return request.user.role == "admin" or memberships.exists()


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsOrganizationMemberOrPlatformAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Organization.objects.all().order_by("id")
        return Organization.objects.filter(
            memberships__user=user, memberships__is_active=True
        ).distinct().order_by("id")

    @action(
        detail=True,
        methods=["get"],
        url_path="user-search",
        permission_classes=[permissions.IsAuthenticated],
    )
    def user_search(self, request, pk=None):
        organization = self.get_object()
        if request.user.role != "admin" and not Membership.objects.filter(
            user=request.user,
            organization=organization,
            role__in=("owner", "admin"),
            is_active=True,
        ).exists():
            raise PermissionDenied("Only organization owners and admins can search for members.")

        term = request.query_params.get("search", "").strip()
        if len(term) < 2:
            return Response([])
        if len(term) > 100:
            raise ValidationError({"search": "Search must be 100 characters or fewer."})

        active_member_ids = Membership.objects.filter(
            organization=organization, is_active=True
        ).values_list("user_id", flat=True)
        users = User.objects.filter(is_active=True).filter(
            Q(username__icontains=term) | Q(email__icontains=term)
        ).exclude(pk__in=active_member_ids).order_by("username", "id")
        return Response(list(users.values("id", "username", "email")[:10]))

    def perform_create(self, serializer):
        with transaction.atomic():
            organization = serializer.save()
            Membership.objects.create(user=self.request.user, organization=organization, role="owner", is_active=True)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {
                "detail": (
                    "Organization deletion is unavailable to preserve memberships "
                    "and donation workflow history."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def verify(self, request, pk=None):
        # Only platform administrators can verify organizations
        if request.user.role != "admin":
            return Response({"detail": "Only platform administrators can verify organizations."}, status=status.HTTP_403_FORBIDDEN)
        organization = self.get_object()
        organization.status = "verified"
        organization.verified_at = timezone.now()
        organization.verified_by = request.user
        organization.save()
        log_audit(
            user=request.user, action='verify', object_type='organization',
            object_id=organization.pk, object_repr=str(organization),
            request=request,
        )
        serializer = self.get_serializer(organization)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def reject(self, request, pk=None):
        if request.user.role != "admin":
            return Response({"detail": "Only platform administrators can reject organizations."}, status=status.HTTP_403_FORBIDDEN)
        organization = self.get_object()
        organization.status = "rejected"
        organization.verified_at = timezone.now()
        organization.verified_by = request.user
        organization.save()
        log_audit(
            user=request.user, action='reject', object_type='organization',
            object_id=organization.pk, object_repr=str(organization),
            request=request,
        )
        serializer = self.get_serializer(organization)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def pending(self, request, pk=None):
        if request.user.role != "admin":
            return Response({"detail": "Only platform administrators can reset verification status."}, status=status.HTTP_403_FORBIDDEN)
        organization = self.get_object()
        organization.status = "pending"
        organization.verified_at = None
        organization.verified_by = None
        organization.save()
        serializer = self.get_serializer(organization)
        return Response(serializer.data)


class IsMembershipManagerOrSelfOrPlatformAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Platform administrators can perform any action
        if request.user.role == "admin":
            return True
        # Allow users to view their own membership
        if obj.user == request.user:
            return True
        # Allow organization owners and admins to manage memberships
        return Membership.objects.filter(user=request.user, organization=obj.organization, role__in=["owner", "admin"], is_active=True).exists()


def get_user_role_level(user, organization):
    """Return the role level of the user in the organization, or 0 if not a member."""
    try:
        membership = Membership.objects.get(user=user, organization=organization, is_active=True)
    except Membership.DoesNotExist:
        return 0
    role = membership.role
    # Define role hierarchy: higher number means higher role
    role_levels = {
        "owner": 4,
        "admin": 3,
        "member": 2,
        "volunteer": 1,
    }
    return role_levels.get(role, 0)


class MembershipViewSet(viewsets.ModelViewSet):
    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer
    permission_classes = [IsMembershipManagerOrSelfOrPlatformAdmin]

    def get_queryset(self):
        user = self.request.user
        organization_id = self.request.query_params.get("organization")
        if organization_id:
            if user.role == "admin":
                return Membership.objects.select_related('user').filter(organization_id=organization_id).order_by("id")
            # Check if the user is an owner or admin of the specified organization
            if Membership.objects.filter(user=user, organization_id=organization_id, role__in=["owner", "admin"], is_active=True).exists():
                return Membership.objects.select_related('user').filter(organization_id=organization_id).order_by("id")
            return Membership.objects.none()
        return Membership.objects.select_related('user').filter(user=user).order_by("id")

    def perform_create(self, serializer):
        organization = serializer.validated_data.get("organization")
        user_to_add = serializer.validated_data.get("user")
        role_to_set = serializer.validated_data.get("role", "member")  # default to member if not provided
        if not organization or not user_to_add:
            return

        # Platform administrators can add any membership with any role
        if self.request.user.role == "admin":
            serializer.save()
            return

        if not Membership.objects.filter(
            user=self.request.user,
            organization=organization,
            role__in=("owner", "admin"),
            is_active=True,
        ).exists():
            raise PermissionDenied("Only organization owners and admins can add members.")

        # Check if the requesting user is an owner or admin of the organization
        requester_role_level = get_user_role_level(self.request.user, organization)
        if requester_role_level == 0:
            raise PermissionDenied("You are not a member of this organization.")

        # Determine the level of the role to set
        role_levels = {
            "owner": 4,
            "admin": 3,
            "member": 2,
            "volunteer": 1,
        }
        new_role_level = role_levels.get(role_to_set, 0)
        if new_role_level == 0:
            raise ValidationError({"role": "Invalid role."})

        # Prevent role escalation: the new role must not be higher than the requester's role
        if new_role_level > requester_role_level:
            raise PermissionDenied("You cannot assign a role higher than your own.")

        serializer.save()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if "user" in request.data or "organization" in request.data:
            return Response({"detail": "User and organization fields cannot be changed."}, status=status.HTTP_400_BAD_REQUEST)
        if "role" in request.data:
            organization = instance.organization
            new_role = request.data["role"]
            # Prevent role escalation
            requester_role_level = (
                5 if request.user.role == "admin"
                else get_user_role_level(request.user, organization)
            )
            if requester_role_level == 0:
                return Response({"detail": "You are not a member of this organization."}, status=status.HTTP_403_FORBIDDEN)
            role_levels = {
                "owner": 4,
                "admin": 3,
                "member": 2,
                "volunteer": 1,
            }
            new_role_level = role_levels.get(new_role, 0)
            if new_role_level == 0:
                return Response({"detail": "Invalid role."}, status=status.HTTP_400_BAD_REQUEST)
            if new_role_level > requester_role_level:
                return Response({"detail": "You cannot assign a role higher than your own."}, status=status.HTTP_403_FORBIDDEN)
            # Prevent removal of the last owner
            if new_role != "owner" and instance.role == "owner":
                owner_count = Membership.objects.filter(organization=organization, role="owner", is_active=True).count()
                if owner_count == 1:
                    return Response({"detail": "Cannot remove the last owner of the organization."}, status=status.HTTP_400_BAD_REQUEST)
        if "is_active" in request.data:
            new_is_active = request.data["is_active"]
            if (
                new_is_active is True
                and not instance.is_active
                and instance.user_id == request.user.pk
                and request.user.role != "admin"
                and not Membership.objects.filter(
                    user=request.user, organization=instance.organization,
                    role__in=("owner", "admin"), is_active=True,
                ).exists()
            ):
                raise PermissionDenied("Only an organization owner or admin can reactivate a membership.")
            if isinstance(new_is_active, bool) and not new_is_active:
                # Deactivation
                organization = instance.organization
                if instance.role == "owner":
                    owner_count = Membership.objects.filter(organization=organization, role="owner", is_active=True).exclude(id=instance.id).count()
                    if owner_count == 0:
                        return Response({"detail": "Cannot deactivate the last owner of the organization."}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Prevent deletion of the last owner
        if instance.role == "owner":
            organization = instance.organization
            owner_count = Membership.objects.filter(organization=organization, role="owner", is_active=True).exclude(id=instance.id).count()
            if owner_count == 0:
                return Response({"detail": "Cannot delete the last owner of the organization."}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)
