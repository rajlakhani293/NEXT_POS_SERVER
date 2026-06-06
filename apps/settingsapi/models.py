# type: ignore
from django.db import models
from apps.common.models import CompanyAwareModel, TenantAwareModel


class Setting(TenantAwareModel):
    key = models.CharField(max_length=150)
    value = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "key")]


class BusinessSetting(CompanyAwareModel):
    allow_partial_orders = models.BooleanField(default=False)
    enable_customer_rewards = models.BooleanField(default=False)
    enable_credit_account = models.BooleanField(default=False)
    enable_cash_registers = models.BooleanField(default=True)
    order_types = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Business Setting"
        verbose_name_plural = "Business Settings"
        constraints = [
            models.UniqueConstraint(fields=["company"], name="unique_business_setting_company"),
        ]

    def __str__(self):
        return f"{self.company.name} Business Settings"
