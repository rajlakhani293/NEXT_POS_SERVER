# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


PAYMENT_TYPES = [
    ("cash", "Cash"),
    ("online", "Online"),
    ("bank", "Bank"),
    ("partial", "Partial"),
    ("card", "Card"),
]


def paymentTypeOptions():
    return [{"value": value, "label": label} for value, label in PAYMENT_TYPES]


def paymentTypeValues():
    return [value for value, _label in PAYMENT_TYPES]


class SalePayment(TenantAwareModel):
    sale_order = models.ForeignKey("sales.SaleOrder", on_delete=models.CASCADE, related_name="payments")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default="cash")
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField()
    reference_number = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)


class RefundPayment(TenantAwareModel):
    return_order = models.ForeignKey("sales.ReturnOrder", on_delete=models.CASCADE, related_name="refund_payments")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default="cash")
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="refund_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    refunded_at = models.DateTimeField()
    reference_number = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)
