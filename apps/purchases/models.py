from django.db import models

from apps.common.models import TenantAwareModel


class Supplier(TenantAwareModel):
    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["name"]


class PurchaseOrder(TenantAwareModel):
    STATUSES = [
        ("draft", "Draft"),
        ("ordered", "Ordered"),
        ("received", "Received"),
        ("partial", "Partially Received"),
        ("cancelled", "Cancelled"),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    code = models.CharField(max_length=50)
    order_date = models.DateField()
    expected_date = models.DateField(blank=True, null=True)
    workflow_status = models.CharField(max_length=20, choices=STATUSES, default="draft")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["-order_date", "-id"]


class PurchaseItem(TenantAwareModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="purchase_items")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="purchase_items")
    ordered_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    received_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2)


class PurchasePayment(TenantAwareModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="payments")
    payment_method = models.ForeignKey("payments.PaymentMethod", on_delete=models.PROTECT, related_name="purchase_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField()
    reference_number = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)
