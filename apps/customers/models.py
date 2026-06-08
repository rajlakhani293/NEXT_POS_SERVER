# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class CustomerGroup(TenantAwareModel):
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=150)
    description = models.TextField(blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reward_system = models.ForeignKey(
        "rewards.RewardSystem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_groups",
    )

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class Customer(TenantAwareModel):
    CUSTOMER_TYPES = [
        ("retail", "Retail"),
        ("wholesale", "Wholesale"),
        ("walk_in", "Walk In"),
    ]

    group = models.ForeignKey(
        CustomerGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
    )
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPES, default="retail")
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    code = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    birth_date = models.DateField(blank=True, null=True)
    gst_number = models.CharField(max_length=50, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_limit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    owed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_sales_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class CustomerAddress(TenantAwareModel):
    ADDRESS_TYPES = [
        ("billing", "Billing"),
        ("shipping", "Shipping"),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES)
    address_line_1 = models.CharField(max_length=255, blank=True)
    pincode = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.ForeignKey(
        "organizations.StateMaster",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_addresses",
    )

    class Meta:
        ordering = ["customer_id", "address_type"]


class CustomerWalletTransaction(TenantAwareModel):
    ENTRY_TYPES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
        ("refund", "Refund"),
        ("payment", "Payment"),
        ("adjustment", "Adjustment"),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="wallet_transactions",
    )
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveBigIntegerField(blank=True, null=True)


class CustomerCreditLedger(TenantAwareModel):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="credit_entries",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    direction = models.CharField(max_length=10, choices=[("increase", "Increase"), ("decrease", "Decrease")])
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reason = models.CharField(max_length=120)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveBigIntegerField(blank=True, null=True)
    note = models.TextField(blank=True)


class CustomerAccountHistory(TenantAwareModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="account_history")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    action = models.CharField(max_length=20, choices=[("credit", "Credit"), ("debit", "Debit")])
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveBigIntegerField(blank=True, null=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
