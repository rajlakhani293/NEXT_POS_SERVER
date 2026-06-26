# type: ignore
from django.contrib.auth.models import UserManager
from django.db import models
from django.db.models import Q

from apps.accounts.models import User
from apps.common.models import TenantAwareModel
from apps.promotions.models import Coupon
from apps.rewards.models import RewardSystem

CUSTOMER_ROLE_CODE = "nexopos.store.customer"


class CustomerGroup(TenantAwareModel):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    minimal_credit_payment = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Minimum percentage the customer must pay when creating a credit sale.",
    )
    reward_system = models.ForeignKey(RewardSystem, on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_groups")

    class Meta:
        db_table = "customers_groups"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomerManager(UserManager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                Q(role_relations__role__namespace=CUSTOMER_ROLE_CODE, role_relations__status=0)
                | Q(role__namespace=CUSTOMER_ROLE_CODE)
            )
            .distinct()
        )


class Customer(User):
    objects = CustomerManager()

    class Meta:
        proxy = True
        ordering = ["first_name", "last_name", "id"]

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.name or self.email or self.phone or f"Customer #{self.pk}"


class CustomerAddress(TenantAwareModel):
    ADDRESS_TYPES = [
        ("billing", "Billing"),
        ("shipping", "Shipping"),
    ]

    customer = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    type = models.CharField(max_length=20, choices=ADDRESS_TYPES, default="billing")
    email = models.EmailField(blank=True)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address_1 = models.CharField(max_length=255, blank=True)
    address_2 = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    pobox = models.CharField(max_length=50, blank=True)
    company_name = models.CharField(max_length=255, blank=True, db_column="company")

    class Meta:
        db_table = "customers_addresses"
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "type"],
                name="unique_customer_address_type",
            ),
        ]
        ordering = ["customer_id", "type"]

    def __str__(self):
        return f"{self.customer} - {self.get_type_display()}"


class CustomerAccountHistory(TenantAwareModel):
    OPERATIONS = [
        ("deduct", "Deduct"),
        ("refund", "Refund"),
        ("add", "Add"),
        ("payment", "Payment"),
    ]

    customer = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="account_history")
    order = models.ForeignKey(
        "sales.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_account_history",
    )
    previous_amount = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    next_amount = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    operation = models.CharField(max_length=20, choices=OPERATIONS, default="add")
    description = models.TextField(blank=True)

    class Meta:
        db_table = "customers_account_history"
        ordering = ["-created_at", "-id"]


class CustomerCoupon(TenantAwareModel):
    name = models.CharField(max_length=150, blank=True, default="")
    usage = models.PositiveIntegerField(default=0)
    limit_usage = models.PositiveIntegerField(default=0)
    code = models.CharField(max_length=150)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="issued_coupons")
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="coupons")

    class Meta:
        db_table = "customers_coupons"
        unique_together = [("customer", "code")]


class CustomerReward(TenantAwareModel):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reward_balances")
    reward = models.ForeignKey(RewardSystem, on_delete=models.CASCADE, related_name="customer_rewards", db_column="reward_id")
    reward_name = models.CharField(max_length=150, blank=True, default="")
    points = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    target = models.DecimalField(max_digits=18, decimal_places=5, default=0)

    class Meta:
        db_table = "customers_rewards"
        unique_together = [("customer", "reward")]
