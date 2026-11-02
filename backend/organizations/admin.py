from django.contrib import admin
from django.utils import timezone

from .models import Membership, Organization


def is_platform_admin(user):
    """Match the app's platform-admin role while requiring admin-site access."""
    return bool(
        user.is_authenticated
        and (user.is_superuser or (user.is_staff and user.role == 'admin'))
    )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'org_type', 'status', 'city', 'country', 'created_at')
    list_filter = ('status', 'org_type', 'country')
    search_fields = ('name', 'email', 'city', 'id')
    ordering = ('name', 'id')
    readonly_fields = ('verified_at', 'verified_by', 'created_at', 'updated_at')
    list_per_page = 50

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not is_platform_admin(request.user):
            readonly.append('status')
        return tuple(readonly)

    def has_delete_permission(self, request, obj=None):
        # Organization deletion cascades to memberships and other related data.
        return False

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = Organization.objects.only('status').get(pk=obj.pk).status

        if obj.status != previous_status and is_platform_admin(request.user):
            if obj.status == 'pending':
                obj.verified_at = None
                obj.verified_by = None
            else:
                obj.verified_at = timezone.now()
                obj.verified_by = request.user

        super().save_model(request, obj, form, change)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'role', 'is_active', 'joined_at')
    list_filter = ('role', 'is_active', 'organization__org_type')
    search_fields = ('user__username', 'user__email', 'organization__name')
    ordering = ('organization__name', 'user__username', 'id')
    readonly_fields = ('user', 'organization', 'role', 'is_active', 'joined_at')
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
