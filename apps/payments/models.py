# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel
from apps.common.tenantDefaults import DEFAULT_PAYMENT_TYPES


PAYMENT_TYPES = [
    ("cash-payment", "Cash"),
    ("bank-payment", "Bank Payment"),
    ("account-payment", "Customer Account"),
]

def paymentTypeOptions():
    return [{"value": value, "label": label} for value, label in PAYMENT_TYPES]


def paymentTypeValues():
    return [value for value, _label in PAYMENT_TYPES]


class PaymentType(TenantAwareModel):
    label = models.CharField(max_length=120)
    identifier = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    readonly = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "payments_types"
        unique_together = [("branch", "identifier"), ("branch", "label")]
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label
