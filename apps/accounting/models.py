# type:ignore
from django.db import models
from apps.common.models import TenantAwareModel


class TransactionAccount(TenantAwareModel):
    ACCOUNT_TYPES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("income", "Income"),
        ("expense", "Expense"),
        ("equity", "Equity"),
    ]

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=80, blank=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    description = models.TextField(blank=True)
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_system = models.BooleanField(default=False)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["account_type", "name"]

    def __str__(self):
        return self.name


class Transaction(TenantAwareModel):
    TRANSACTION_TYPES = [
        ("income", "Income"),
        ("expense", "Expense"),
        ("transfer", "Transfer"),
        ("adjustment", "Adjustment"),
    ]
    SOURCE_TYPES = [
        ("sale", "Sale"),
        ("purchase", "Purchase"),
        ("expense", "Expense"),
        ("cash_register", "Cash Register"),
        ("customer_credit", "Customer Credit"),
        ("manual", "Manual"),
        ("system", "System"),
    ]

    account = models.ForeignKey(TransactionAccount, on_delete=models.PROTECT, related_name="transactions")
    name = models.CharField(max_length=180)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    source_type = models.CharField(max_length=40, choices=SOURCE_TYPES, default="manual")
    source_id = models.PositiveBigIntegerField(blank=True, null=True)
    value = models.DecimalField(max_digits=14, decimal_places=2)
    transaction_date = models.DateTimeField()
    description = models.TextField(blank=True)
    reference_number = models.CharField(max_length=150, blank=True)
    is_recurring = models.BooleanField(default=False)
    recurring_rule = models.CharField(max_length=80, blank=True)
    next_run_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="accounting_transactions",
    )

    class Meta:
        ordering = ["-transaction_date", "-id"]

    def __str__(self):
        return self.name


class TransactionHistory(TenantAwareModel):
    ACTION_TYPES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
    ]

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="histories")
    account = models.ForeignKey(TransactionAccount, on_delete=models.PROTECT, related_name="histories")
    action_type = models.CharField(max_length=10, choices=ACTION_TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    balance_before = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.PositiveBigIntegerField(blank=True, null=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.action_type} {self.amount}"


class ActiveTransactionHistory(TenantAwareModel):
    transaction_history = models.OneToOneField(
        TransactionHistory,
        on_delete=models.CASCADE,
        related_name="active_marker",
    )
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="active_histories")
    account = models.ForeignKey(TransactionAccount, on_delete=models.PROTECT, related_name="active_histories")
    action_type = models.CharField(max_length=10, choices=TransactionHistory.ACTION_TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.PositiveBigIntegerField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class TransactionBalanceDay(TenantAwareModel):
    account = models.ForeignKey(TransactionAccount, on_delete=models.CASCADE, related_name="daily_balances")
    balance_date = models.DateField()
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        unique_together = [("branch", "account", "balance_date")]
        ordering = ["-balance_date"]


class TransactionBalanceMonth(TenantAwareModel):
    account = models.ForeignKey(TransactionAccount, on_delete=models.CASCADE, related_name="monthly_balances")
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        unique_together = [("branch", "account", "year", "month")]
        ordering = ["-year", "-month"]


class TransactionActionRule(TenantAwareModel):
    source_type = models.CharField(max_length=40)
    action_name = models.CharField(max_length=80)
    debit_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="debit_rules",
        blank=True,
        null=True,
    )
    credit_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="credit_rules",
        blank=True,
        null=True,
    )
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        unique_together = [("branch", "source_type", "action_name")]
        ordering = ["source_type", "action_name"]

    def __str__(self):
        return f"{self.source_type}: {self.action_name}"
