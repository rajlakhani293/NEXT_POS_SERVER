# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class CashRegister(TenantAwareModel):
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=120)
    location = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["name"]


class CashierShift(TenantAwareModel):
    STATUSES = [("open", "Open"), ("closed", "Closed"), ("suspended", "Suspended")]

    register = models.ForeignKey(CashRegister, on_delete=models.PROTECT, related_name="shifts")
    cashier = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="cashier_shifts")
    opened_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="opened_shifts")
    closed_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="closed_shifts")
    shift_status = models.CharField(max_length=20, choices=STATUSES, default="open")
    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField(blank=True, null=True)
    opening_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expected_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    declared_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    difference_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_sales_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_refund_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cash_in = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cash_out = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    note = models.TextField(blank=True)


class CashRegisterEntry(TenantAwareModel):
    ENTRY_TYPES = [
        ("opening", "Opening"),
        ("sale_payment", "Sale Payment"),
        ("change_given", "Change Given"),
        ("refund", "Refund"),
        ("cash_in", "Cash In"),
        ("cash_out", "Cash Out"),
        ("expense", "Expense"),
        ("closing", "Closing"),
    ]

    shift = models.ForeignKey(CashierShift, on_delete=models.CASCADE, related_name="entries")
    register = models.ForeignKey(CashRegister, on_delete=models.CASCADE, related_name="entries")
    cashier = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="register_entries")
    payment_type = models.CharField(max_length=80, blank=True, default="")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveBigIntegerField(blank=True, null=True)
    note = models.TextField(blank=True)
