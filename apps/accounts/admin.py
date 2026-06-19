# type: ignore
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import AccessToken, PermissionAccess, Role, User, UserRoleRelation
from apps.common.admin import SmartModelAdmin


@admin.register(Role)
class RoleAdmin(SmartModelAdmin):
    filter_horizontal = ("permissions",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "id",
        "username",
        "full_name",
        "email",
        "phone",
        "company",
        "branch",
        "role",
        "is_active",
        "is_staff",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "company",
        "branch",
        "role",
    )
    search_fields = ("username", "full_name", "email", "phone")
    readonly_fields = ("last_login", "date_joined")
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Business Access",
            {
                "fields": (
                    "full_name",
                    "phone",
                    "company",
                    "branch",
                    "role",
                )
            },
        ),
    )


@admin.register(UserRoleRelation)
class UserRoleRelationAdmin(SmartModelAdmin):
    list_display = ("id", "user", "role", "status", "created_at")
    list_filter = ("status", "role")
    search_fields = ("user__username", "user__full_name", "role__name", "role__namespace")


@admin.register(PermissionAccess)
class PermissionAccessAdmin(SmartModelAdmin):
    list_display = ("id", "requester", "granter", "permission", "access_status", "status", "created_at")
    list_filter = ("access_status", "status")
    search_fields = ("requester__username", "granter__username", "permission", "url")


@admin.register(AccessToken)
class AccessTokenAdmin(SmartModelAdmin):
    list_display = (
        "id",
        "user",
        "device_name",
        "expires_at",
        "last_used_at",
        "status",
        "created_at",
    )
    search_fields = ("user__username", "user__full_name", "token", "device_name")
    readonly_fields = ("token", "created_at", "updated_at", "deleted_at")
