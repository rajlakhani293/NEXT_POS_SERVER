# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class DashboardDay(TenantAwareModel):
    range_starts = models.DateTimeField()
    range_ends = models.DateTimeField()
    day_of_year = models.PositiveIntegerField(default=0)
    total_unpaid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_unpaid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_unpaid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_unpaid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_paid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_paid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_paid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_paid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_partially_paid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_partially_paid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_partially_paid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_partially_paid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_income = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_income = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_discounts = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_discounts = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_taxes = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_taxes = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_wasted_goods_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_wasted_goods_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_wasted_goods = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_wasted_goods = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_expenses = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    day_expenses = models.DecimalField(max_digits=18, decimal_places=5, default=0)

    class Meta:
        db_table = "dashboard_days"
        unique_together = [("branch", "range_starts", "range_ends")]
        ordering = ["-range_starts"]


class DashboardWeek(TenantAwareModel):
    range_starts = models.DateTimeField()
    range_ends = models.DateTimeField()
    week_number = models.PositiveIntegerField(default=0)
    total_gross_income = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_taxes = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_expenses = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_net_income = models.DecimalField(max_digits=18, decimal_places=5, default=0)

    class Meta:
        db_table = "dashboard_weeks"
        unique_together = [("branch", "range_starts", "range_ends")]
        ordering = ["-range_starts"]


class DashboardMonth(TenantAwareModel):
    range_starts = models.DateTimeField()
    range_ends = models.DateTimeField()
    month_taxes = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_unpaid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_unpaid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_paid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_paid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_partially_paid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_partially_paid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_income = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_discounts = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_wasted_goods_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_wasted_goods = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_expenses = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_wasted_goods = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_unpaid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_unpaid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_paid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_paid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_partially_paid_orders = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_partially_paid_orders_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_income = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_discounts = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_taxes = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_wasted_goods_count = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    total_expenses = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    month_of_year = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "dashboard_months"
        unique_together = [("branch", "range_starts", "range_ends")]
        ordering = ["-range_starts"]
