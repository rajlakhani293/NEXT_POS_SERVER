# type: ignore
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import AccessToken, OtpRequest, Role, User
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
        "auth_provider",
        "is_active",
        "is_staff",
        "onboarding_completed",
    )
    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "auth_provider",
        "company",
        "branch",
        "role",
        "onboarding_completed",
        "is_phone_verified",
        "is_email_verified",
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
                    "auth_provider",
                    "google_sub",
                    "is_phone_verified",
                    "is_email_verified",
                    "onboarding_completed",
                    "is_cashier",
                    "is_store_manager",
                )
            },
        ),
    )


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


@admin.register(OtpRequest)
class OtpRequestAdmin(SmartModelAdmin):
    list_display = (
        "id",
        "phone",
        "purpose",
        "code",
        "expires_at",
        "verified_at",
        "attempts",
        "status",
    )
    search_fields = ("phone", "code")
    list_filter = ("purpose", "status")
