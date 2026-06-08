# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class ExpenseCategory(TenantAwareModel):
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["name"]


class ExpenseEntry(TenantAwareModel):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name="expenses")
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    payment_type = models.CharField(max_length=80, blank=True, default="")
    note = models.TextField(blank=True)
    reference_number = models.CharField(max_length=120, blank=True)
