# type: ignore
from django.db import models
from apps.common.models import BaseModel, CompanyAwareModel


class BusinessSetting(CompanyAwareModel):
    allow_partial_orders = models.BooleanField(default=False)
    enable_customer_rewards = models.BooleanField(default=False)
    enable_credit_account = models.BooleanField(default=False)
    enable_cash_registers = models.BooleanField(default=True)
    allow_decimal_quantities = models.BooleanField(default=True)
    quick_product_enabled = models.BooleanField(default=True)
    show_quantity = models.BooleanField(default=True)
    currency_precision = models.PositiveSmallIntegerField(default=2)
    hide_empty_categories = models.BooleanField(default=True)
    unit_price_editable = models.BooleanField(default=True)
    default_change_payment_type = models.CharField(
        max_length=80,
        default="cash-payment",
    )
    order_types = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Business Setting"
        verbose_name_plural = "Business Settings"
        constraints = [
            models.UniqueConstraint(fields=["company"], name="unique_business_setting_company"),
        ]

    def __str__(self):
        return f"{self.company.name} Business Settings"


class Option(BaseModel):
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="options",
        db_column="user_id",
    )
    key = models.CharField(max_length=255)
    value = models.TextField(blank=True, null=True)
    expire_on = models.DateTimeField(blank=True, null=True)
    array = models.BooleanField(default=False)

    class Meta:
        db_table = "options"
        ordering = ["key", "id"]

    def __str__(self):
        return self.key


class Job(models.Model):
    queue = models.CharField(max_length=255, db_index=True)
    payload = models.TextField()
    attempts = models.PositiveSmallIntegerField()
    reserved_at = models.PositiveIntegerField(blank=True, null=True)
    available_at = models.PositiveIntegerField()
    created_at = models.PositiveIntegerField()

    class Meta:
        db_table = "jobs"

    def __str__(self):
        return f"{self.queue}#{self.id}"


class FailedJob(models.Model):
    connection = models.TextField()
    queue = models.TextField()
    payload = models.TextField()
    exception = models.TextField()
    failed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "failed_jobs"

    def __str__(self):
        return f"{self.queue} failed #{self.id}"
