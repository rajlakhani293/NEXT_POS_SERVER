# type: ignore
from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.utils import timezone
from apps.common.models import BaseModel, SoftDeleteModel, TenantAwareModel
from apps.common.commonQuery import commonQuery

class Role(TenantAwareModel):
    ADMIN = "admin"
    STOREADMIN = "store-administrator"
    STORECASHIER = "store-cashier"
    STORECUSTOMER = "store-customer"
    USER = "user"
    DRIVER = "driver"

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

    @classmethod
    def findByNamespace(cls, namespace, company_id=None, branch_id=None):
        queryset = commonQuery.scopedQueryset(cls, {"namespace": namespace, "status__in": [0, 1]}, tenant_config={})
        if company_id is not None:
            queryset = queryset.filter(company_id=company_id)
        if branch_id is not None:
            queryset = queryset.filter(branch_id=branch_id)
        return queryset.first()

    def addPermissions(self, permissions, silent=False):
        if isinstance(permissions, str):
            permissions = [permissions]
        permission_qs = Permission.objects.filter(codename__in=list(permissions or []))
        self.permissions.add(*permission_qs)

    def removePermissions(self, permissions):
        if isinstance(permissions, str):
            permissions = [permissions]
        permission_qs = Permission.objects.filter(codename__in=list(permissions or []))
        self.permissions.remove(*permission_qs)


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
    activation_token = models.CharField(max_length=255, blank=True, null=True)
    activation_expiration = models.DateTimeField(blank=True, null=True)
    remember_token = models.CharField(max_length=100, blank=True, null=True)
    status = models.IntegerField(
        choices=SoftDeleteModel.STATUS_CHOICES,
        default=SoftDeleteModel.STATUS_ACTIVE,
        help_text="0: Active, 1: Inactive, 2: Deleted.",
    )
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.full_name or self.phone or self.email or self.username

    def assignRole(self, role_name):
        from apps.common.commonQuery import commonQuery

        role = Role.findByNamespace(role_name, self.company_id, self.branch_id)
        if role is None:
            return {"status": "error", "message": "Unable to identify the provided role."}
        commonQuery.getOrCreateRecord(
            UserRoleRelation,
            {
                "user": self,
                "role": role,
            },
            defaults={
                "company_id": self.company_id,
                "branch_id": self.branch_id,
                "status": 0,
            },
            tenant_config={},
            return_plain=False,
        )
        return {"status": "success", "message": "The role was successfully assigned."}

    def roleNamespaces(self):
        return list(
            self.role_relations.filter(status=0)
            .select_related("role")
            .values_list("role__namespace", flat=True)
        )

    def hasRoles(self, roles):
        return bool(set(self.roleNamespaces()) & set(roles))

    def allowedTo(self, permissions):
        permissions = permissions if isinstance(permissions, list) else [permissions]
        return self.role_relations.filter(
            status=0,
            role__permissions__codename__in=permissions,
        ).exists()


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


class PermissionAccess(BaseModel):
    GRANTED = "granted"
    DENIED = "denied"
    PENDING = "pending"
    EXPIRED = "expired"
    USED = "used"

    ACCESS_STATUS_CHOICES = [
        (GRANTED, "Granted"),
        (DENIED, "Denied"),
        (PENDING, "Pending"),
        (EXPIRED, "Expired"),
        (USED, "Used"),
    ]

    requester = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="permission_access_requests",
    )
    granter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="permission_access_grants",
    )
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.CASCADE,
        related_name="permission_accesses",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.CASCADE,
        related_name="permission_accesses",
    )
    permission = models.CharField(max_length=255, db_index=True)
    url = models.CharField(max_length=255, blank=True, null=True)
    access_status = models.CharField(max_length=20, choices=ACCESS_STATUS_CHOICES, default=PENDING)
    expired_at = models.DateTimeField(blank=True, null=True)
    status = models.IntegerField(
        choices=SoftDeleteModel.STATUS_CHOICES,
        default=SoftDeleteModel.STATUS_ACTIVE,
        help_text="0: Active, 1: Inactive, 2: Deleted.",
    )
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "permissions_access"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.permission} - {self.access_status}"


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
