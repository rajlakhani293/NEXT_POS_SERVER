# type: ignore
from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.utils import timezone
from apps.common.models import BaseModel, SoftDeleteModel


class Role(BaseModel):
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.CASCADE,
        related_name="roles",
    )
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=150)
    description = models.TextField(blank=True)
    is_cashier = models.BooleanField(default=False)
    is_store_manager = models.BooleanField(default=False)
    permissions = models.ManyToManyField(Permission, blank=True, related_name="roles")

    class Meta:
        unique_together = [("company", "code")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    AUTH_PROVIDER_CHOICES = [
        ("otp", "OTP"),
        ("google", "Google"),
    ]

    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    full_name = models.CharField(max_length=255, blank=True)
    profile_image = models.URLField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    auth_provider = models.CharField(max_length=20, choices=AUTH_PROVIDER_CHOICES, default="password")
    google_sub = models.CharField(max_length=255, blank=True, unique=True, null=True)
    is_phone_verified = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    onboarding_completed = models.BooleanField(default=False)
    is_cashier = models.BooleanField(default=False)
    is_store_manager = models.BooleanField(default=False)
    status = models.IntegerField(
        choices=SoftDeleteModel.STATUS_CHOICES,
        default=SoftDeleteModel.STATUS_ACTIVE,
        help_text="0: Active, 1: Inactive, 2: Deleted.",
    )
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.full_name or self.phone or self.email or self.username


class AccessToken(BaseModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="access_tokens",
    )
    token = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(blank=True, null=True)
    device_name = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()


class OtpRequest(BaseModel):
    PURPOSE_CHOICES = [
        ("login", "Login"),
        ("signup", "Signup"),
    ]

    phone = models.CharField(max_length=20)
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default="login")
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(blank=True, null=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()


class UserRoleRelation(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_relations")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_relations")
    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE, related_name="user_role_relations")
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, null=True, blank=True, related_name="user_role_relations")

    class Meta:
        unique_together = [("user", "role", "branch")]


class PermissionAccess(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="permission_accesses", null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permission_accesses", null=True, blank=True)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="access_records")
    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE, related_name="permission_accesses")
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, null=True, blank=True, related_name="permission_accesses")
    is_allowed = models.BooleanField(default=True)


class UserScope(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scopes")
    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE, related_name="user_scopes")
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, null=True, blank=True, related_name="user_scopes")
    scope_type = models.CharField(max_length=40, default="branch")
    scope_value = models.CharField(max_length=120, blank=True)


class UserAttribute(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="attributes")
    key = models.CharField(max_length=120)
    value = models.TextField(blank=True)

    class Meta:
        unique_together = [("user", "key")]


class UserWidget(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="widgets")
    widget_key = models.CharField(max_length=120)
    title = models.CharField(max_length=150, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)

    class Meta:
        unique_together = [("user", "widget_key")]
