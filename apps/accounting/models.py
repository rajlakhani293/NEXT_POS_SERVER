# type:ignore
from django.db import models
from apps.common.models import TenantAwareModel


class TransactionAccount(TenantAwareModel):
    name = models.CharField(max_length=150)
    account = models.CharField(max_length=120, blank=True)
    sub_category = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sub_accounts",
    )
    category_identifier = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "transactions_accounts"
        unique_together = [("branch", "account"), ("branch", "name")]
        ordering = ["category_identifier", "name"]

    def __str__(self):
        return self.name


class Transaction(TenantAwareModel):
    TYPE_INCOME = "income"
    TYPE_EXPENSE = "expense"

    name = models.CharField(max_length=180)
    account = models.ForeignKey(TransactionAccount, on_delete=models.PROTECT, related_name="transactions")
    description = models.TextField(blank=True, null=True)
    media_id = models.PositiveBigIntegerField(default=0)
    value = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    recurring = models.BooleanField(default=False)
    type = models.CharField(max_length=80, blank=True, null=True, default=TYPE_EXPENSE)
    active = models.BooleanField(default=False)
    group_id = models.PositiveBigIntegerField(blank=True, null=True)
    occurrence = models.CharField(max_length=80, blank=True, null=True)
    occurrence_value = models.CharField(max_length=80, blank=True, null=True)
    scheduled_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "transactions"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name


class TransactionHistory(TenantAwareModel):
    STATUS_ACTIVE_TEXT = "active"
    STATUS_DELETING_TEXT = "deleting"
    STATUS_PENDING_TEXT = "pending"
    OPERATION_DEBIT = "debit"
    OPERATION_CREDIT = "credit"
    OPERATION_TYPES = [
        (OPERATION_DEBIT, "Debit"),
        (OPERATION_CREDIT, "Credit"),
    ]

    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, null=True, blank=True, related_name="histories")
    operation = models.CharField(max_length=10, choices=OPERATION_TYPES, default=OPERATION_DEBIT)
    transaction_account = models.ForeignKey(TransactionAccount, on_delete=models.PROTECT, null=True, blank=True, related_name="histories")
    rule = models.ForeignKey(
        "TransactionActionRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="histories",
    )
    procurement_id = models.PositiveBigIntegerField(blank=True, null=True)
    order_refund_id = models.PositiveBigIntegerField(blank=True, null=True)
    order_refund_product_id = models.PositiveBigIntegerField(blank=True, null=True)
    order_id = models.PositiveBigIntegerField(blank=True, null=True)
    order_product_id = models.PositiveBigIntegerField(blank=True, null=True)
    order_payment_id = models.PositiveBigIntegerField(blank=True, null=True)
    register_history_id = models.PositiveBigIntegerField(blank=True, null=True)
    customer_account_history_id = models.PositiveBigIntegerField(blank=True, null=True)
    name = models.CharField(max_length=180)
    type = models.CharField(max_length=80, blank=True)
    transaction_status = models.CharField(max_length=30, default=STATUS_PENDING_TEXT, db_column="transaction_status")
    value = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    trigger_date = models.DateTimeField(blank=True, null=True)
    is_reflection = models.BooleanField(default=False)
    reflection_source_id = models.PositiveBigIntegerField(blank=True, null=True)

    class Meta:
        db_table = "transactions_histories"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.operation} {self.value}"


class TransactionBalanceDay(TenantAwareModel):
    opening_balance = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    income = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    expense = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    date = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "transactions_balance_days"
        unique_together = [("branch", "date")]
        ordering = ["-date"]


class TransactionBalanceMonth(TenantAwareModel):
    opening_balance = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    income = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    expense = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    date = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "transactions_balance_months"
        unique_together = [("branch", "date")]
        ordering = ["-date"]


class TransactionActionRule(TenantAwareModel):
    ACTION_CHOICES = [
        ("increase", "Increase"),
        ("decrease", "Decrease"),
    ]

    on = models.CharField(max_length=80, default="")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="primary_rules",
    )
    do = models.CharField(max_length=20, choices=ACTION_CHOICES, default="increase")
    offset_account = models.ForeignKey(
        TransactionAccount,
        on_delete=models.PROTECT,
        related_name="offset_rules",
    )
    locked = models.BooleanField(default=False)

    class Meta:
        db_table = "transactions_actions_rules"
        ordering = ["id"]

    def __str__(self):
        return self.on
