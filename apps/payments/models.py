# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


PAYMENT_TYPES = [
    ("cash-payment", "Cash"),
    ("bank-payment", "Bank Payment"),
    ("account-payment", "Customer Account"),
]

DEFAULT_PAYMENT_TYPES = [
    {
        "identifier": "cash-payment",
        "label": "Cash",
        "description": "Default cash payment method.",
        "sort_order": 0,
    },
    {
        "identifier": "bank-payment",
        "label": "Bank Payment",
        "description": "Default bank payment method.",
        "sort_order": 1,
    },
    {
        "identifier": "account-payment",
        "label": "Customer Account",
        "description": "Default customer account payment method.",
        "sort_order": 2,
    },
]

LEGACY_PAYMENT_TYPE_ALIASES = {
    "cash": "cash-payment",
    "bank": "bank-payment",
    "online": "bank-payment",
    "card": "bank-payment",
    "partial": "account-payment",
}


def paymentTypeOptions():
    return [{"value": value, "label": label} for value, label in PAYMENT_TYPES]


def paymentTypeValues():
    return [value for value, _label in PAYMENT_TYPES]


def normalizePaymentType(value):
    return LEGACY_PAYMENT_TYPE_ALIASES.get(value, value)


class PaymentType(TenantAwareModel):
    label = models.CharField(max_length=120)
    identifier = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    is_enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("branch", "identifier")]
        ordering = ["sort_order", "label"]

    def __str__(self):
        return self.label


class SalePayment(TenantAwareModel):
    sale_order = models.ForeignKey("sales.SaleOrder", on_delete=models.CASCADE, related_name="payments")
    payment_type = models.CharField(max_length=80, default="cash-payment")
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField()
    reference_number = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)


class RefundPayment(TenantAwareModel):
    return_order = models.ForeignKey("sales.ReturnOrder", on_delete=models.CASCADE, related_name="refund_payments")
    payment_type = models.CharField(max_length=80, default="cash-payment")
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="refund_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    refunded_at = models.DateTimeField()
    reference_number = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)
