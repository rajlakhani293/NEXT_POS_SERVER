# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class Register(TenantAwareModel):
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

    register = models.ForeignKey(Register, on_delete=models.CASCADE, related_name="entries")
    cashier = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="register_entries")
    payment_id = models.PositiveBigIntegerField(blank=True, null=True)
    payment_type_id = models.PositiveIntegerField(default=0)
    order_id = models.PositiveBigIntegerField(blank=True, null=True)
    payment_type = models.CharField(max_length=80, blank=True, default="")
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES, db_column="action")
    amount = models.DecimalField(max_digits=18, decimal_places=5, db_column="value")
    balance_before = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    balance_after = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    transaction_type = models.CharField(max_length=20, blank=True, null=True)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveBigIntegerField(blank=True, null=True)
    note = models.TextField(blank=True, db_column="description")

    class Meta:
        db_table = "registers_history"
