from django.db import models

from apps.common.models import TenantAwareModel


class PaymentMethod(TenantAwareModel):
    METHOD_TYPES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("bank", "Bank"),
        ("upi", "UPI"),
        ("wallet", "Wallet"),
        ("credit", "Credit"),
    ]

    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=120)
    method_type = models.CharField(max_length=20, choices=METHOD_TYPES, default="cash")
    is_cash = models.BooleanField(default=False)
    requires_reference = models.BooleanField(default=False)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["name"]


class SalePayment(TenantAwareModel):
    sale_order = models.ForeignKey("sales.SaleOrder", on_delete=models.CASCADE, related_name="payments")
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, related_name="sale_payments")
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField()
    reference_number = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)


class RefundPayment(TenantAwareModel):
    return_order = models.ForeignKey("sales.ReturnOrder", on_delete=models.CASCADE, related_name="refund_payments")
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, related_name="refund_payments")
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="refund_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    refunded_at = models.DateTimeField()
    reference_number = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)
