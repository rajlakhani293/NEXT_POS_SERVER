from django.db import models

from apps.common.models import TenantAwareModel


class DayClosing(TenantAwareModel):
    branch_date = models.DateField()
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="day_closings")
    total_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_returns = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_discounts = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_due_collected = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cash_expected = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cash_declared = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        unique_together = [("branch", "branch_date", "shift")]


class SalesSummarySnapshot(TenantAwareModel):
    snapshot_date = models.DateField()
    gross_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    returns_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    order_count = models.PositiveIntegerField(default=0)
    avg_order_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_items_sold = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    class Meta:
        unique_together = [("branch", "snapshot_date")]
