# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class Register(TenantAwareModel):
    STATUS_OPENED = "opened"
    STATUS_CLOSED = "closed"
    STATUS_DISABLED = "disabled"
    STATUS_INUSE = "in-use"

    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=120, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True, null=True)
    used_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="used_registers", db_column="used_by")
    balance = models.DecimalField(max_digits=18, decimal_places=5, default=0)

    class Meta:
        db_table = "registers"
        unique_together = [("branch", "code")]
        ordering = ["name"]


class RegistersHistory(TenantAwareModel):
    ACTION_OPENING = "register-opening"
    ACTION_CLOSING = "register-closing"
    ACTION_CASHING = "register-cash-in"
    ACTION_CASHOUT = "register-cash-out"
    ACTION_DELETE = "register-cash-delete"
    ACTION_ORDER_PAYMENT = "register-order-payment"
    ACTION_ORDER_CHANGE = "register-order-change"
    ACTION_ORDER_VOUCHER = "register-order-voucher"
    ACTION_REFUND = "register-refund"
    ACTION_ACCOUNT_PAY = "register-account-pay"
    ACTION_ACCOUNT_CHANGE = "register-account-in"

    ENTRY_TYPES = [
        (ACTION_OPENING, "Register Opening"),
        (ACTION_CLOSING, "Register Closing"),
        (ACTION_CASHING, "Cash In"),
        (ACTION_CASHOUT, "Cash Out"),
        (ACTION_DELETE, "Cash Delete"),
        (ACTION_ORDER_PAYMENT, "Order Payment"),
        (ACTION_ORDER_CHANGE, "Order Change"),
        (ACTION_ORDER_VOUCHER, "Order Voucher"),
        (ACTION_REFUND, "Refund"),
        (ACTION_ACCOUNT_PAY, "Account Pay"),
        (ACTION_ACCOUNT_CHANGE, "Account In"),
    ]

    register = models.ForeignKey(Register, on_delete=models.CASCADE, related_name="entries")
    payment_id = models.PositiveBigIntegerField(blank=True, null=True)
    payment_type_id = models.PositiveIntegerField(default=0)
    order_id = models.PositiveBigIntegerField(blank=True, null=True)
    entry_type = models.CharField(max_length=50, choices=ENTRY_TYPES, db_column="action")
    amount = models.DecimalField(max_digits=18, decimal_places=5, db_column="value")
    note = models.TextField(blank=True, null=True, db_column="description")
    balance_before = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    transaction_type = models.CharField(max_length=20, blank=True, null=True)
    balance_after = models.DecimalField(max_digits=18, decimal_places=5, default=0)

    class Meta:
        db_table = "registers_history"
