# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class DashboardDay(TenantAwareModel):
    range_starts = models.DateTimeField()
    range_ends = models.DateTimeField()
    day_of_year = models.PositiveIntegerField()
    day_expenses = models.DecimalField(max_digits=18, decimal_places=5, default=0)

    class Meta:
        db_table = "dashboard_days"
        unique_together = [("branch", "range_starts", "range_ends")]
        ordering = ["-range_starts"]


class DashboardWeek(TenantAwareModel):
    range_starts = models.DateTimeField()
    range_ends = models.DateTimeField()
    week_of_year = models.PositiveIntegerField()
    week_expenses = models.DecimalField(max_digits=18, decimal_places=5, default=0)

    class Meta:
        db_table = "dashboard_weeks"
        unique_together = [("branch", "range_starts", "range_ends")]
        ordering = ["-range_starts"]


class DashboardMonth(TenantAwareModel):
    range_starts = models.DateTimeField()
    range_ends = models.DateTimeField()
    month_of_year = models.PositiveIntegerField()
    total_expenses = models.DecimalField(max_digits=18, decimal_places=5, default=0)

    class Meta:
        db_table = "dashboard_months"
        unique_together = [("branch", "range_starts", "range_ends")]
        ordering = ["-range_starts"]
