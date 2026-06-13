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
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sub_accounts",
    )
    description = models.TextField(blank=True)
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_system = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)

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
    event_key = models.CharField(max_length=80, blank=True)
    group_code = models.CharField(max_length=80, blank=True)
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
    rule = models.ForeignKey(
        "TransactionActionRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="histories",
    )
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
    ACTION_CHOICES = [
        ("increase", "Increase"),
        ("decrease", "Decrease"),
    ]

    event_key = models.CharField(max_length=80)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="primary_rules",
    )
    offset_action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    offset_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="offset_rules",
    )
    is_system = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.event_key


class AccountingSetting(TenantAwareModel):
    expense_accounts = models.ManyToManyField(
        TransactionAccount,
        blank=True,
        related_name="expense_settings",
    )
    paid_expense_offset_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="paid_expense_offset_settings",
    )
    sales_revenue_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="sales_revenue_settings",
    )
    order_cash_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="order_cash_settings",
    )
    receivable_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="receivable_settings",
    )
    cogs_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="cogs_settings",
    )
    inventory_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="inventory_settings",
    )
    procurement_cash_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="procurement_cash_settings",
    )
    procurement_payable_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="procurement_payable_settings",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "branch"],
                name="unique_accounting_setting_branch",
            ),
        ]
