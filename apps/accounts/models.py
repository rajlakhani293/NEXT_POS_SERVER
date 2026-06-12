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
    auth_provider = models.CharField(max_length=20, choices=AUTH_PROVIDER_CHOICES, default="otp")
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
