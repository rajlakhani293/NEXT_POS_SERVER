# type: ignore
from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.utils import timezone
from apps.common.models import BaseModel, SoftDeleteModel, TenantAwareModel


class Role(TenantAwareModel):
    name = models.CharField(max_length=150)
    namespace = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    reward_system_id = models.PositiveBigIntegerField(blank=True, null=True)
    minimal_credit_payment = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    locked = models.BooleanField(default=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name="roles", db_table="role_permission")

    class Meta:
        db_table = "roles"
        unique_together = [("branch", "name"), ("branch", "namespace")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
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
    group = models.ForeignKey(
        "customers.CustomerGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
    )
    full_name = models.CharField(max_length=255, blank=True)
    profile_image = models.URLField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    pobox = models.CharField(max_length=50, blank=True)
    birth_date = models.DateField(blank=True, null=True)
    purchases_amount = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    owed_amount = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    credit_limit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    account_amount = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_sales = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_sales_count = models.PositiveIntegerField(default=0)
    theme = models.CharField(max_length=50, default="light")
    language = models.CharField(max_length=20, default="en")
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


class UserRoleRelation(BaseModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="role_relations",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_relations",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.CASCADE,
        related_name="user_role_relations",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.CASCADE,
        related_name="user_role_relations",
    )
    status = models.IntegerField(
        choices=SoftDeleteModel.STATUS_CHOICES,
        default=SoftDeleteModel.STATUS_ACTIVE,
        help_text="0: Active, 1: Inactive, 2: Deleted.",
    )
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "users_roles_relations"
        unique_together = [("branch", "user", "role")]
        ordering = ["user_id", "role_id"]

    def __str__(self):
        return f"{self.user} - {self.role}"


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
