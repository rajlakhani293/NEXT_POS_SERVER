# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class DashboardDay(TenantAwareModel):
    dashboard_date = models.DateField()
    total_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_purchases = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_customer_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_supplier_payable = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    order_count = models.PositiveIntegerField(default=0)
    purchase_count = models.PositiveIntegerField(default=0)
    expense_count = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("branch", "dashboard_date")]
        ordering = ["-dashboard_date"]


class DashboardMonth(TenantAwareModel):
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    total_sales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_purchases = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_customer_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_supplier_payable = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    order_count = models.PositiveIntegerField(default=0)
    purchase_count = models.PositiveIntegerField(default=0)
    expense_count = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = [("branch", "year", "month")]
        ordering = ["-year", "-month"]
