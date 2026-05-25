from django.db import models

from apps.common.models import TenantAwareModel


class CartDraft(TenantAwareModel):
    code = models.CharField(max_length=50)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cart_drafts",
    )
    cashier = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cart_drafts",
    )
    draft_status = models.CharField(max_length=20, choices=[("active", "Active"), ("held", "Held"), ("converted", "Converted")], default="active")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]


class SaleOrder(TenantAwareModel):
    PAYMENT_STATUSES = [
        ("hold", "Hold"),
        ("unpaid", "Unpaid"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
        ("refunded", "Refunded"),
        ("partially_refunded", "Partially Refunded"),
        ("void", "Void"),
    ]
    ORDER_TYPES = [
        ("pos", "POS"),
        ("takeaway", "Takeaway"),
        ("delivery", "Delivery"),
        ("online", "Online"),
    ]

    customer = models.ForeignKey("customers.Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders")
    cashier = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders")
    register = models.ForeignKey("registers.CashRegister", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders")
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders")
    code = models.CharField(max_length=50)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, default="pos")
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUSES, default="unpaid")
    delivery_status = models.CharField(max_length=30, blank=True)
    process_status = models.CharField(max_length=30, blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    coupon_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tendered_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    change_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    due_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_items = models.PositiveIntegerField(default=0)
    total_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    support_installments = models.BooleanField(default=False)
    final_payment_date = models.DateTimeField(blank=True, null=True)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["-id"]


class SaleItem(TenantAwareModel):
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="sale_items")
    variant = models.ForeignKey("catalog.ProductVariant", on_delete=models.PROTECT, related_name="sale_items")
    unit = models.ForeignKey("catalog.Unit", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_items")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    item_status = models.CharField(max_length=20, default="sold")


class SaleTax(TenantAwareModel):
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="tax_lines")
    tax = models.ForeignKey("catalog.Tax", on_delete=models.PROTECT, related_name="sale_tax_lines")
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=8, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)


class SaleAddress(TenantAwareModel):
    ADDRESS_TYPES = [("billing", "Billing"), ("shipping", "Shipping")]

    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="addresses")
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address_1 = models.CharField(max_length=255, blank=True)
    address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)


class SaleNote(TenantAwareModel):
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="notes")
    title = models.CharField(max_length=150, blank=True)
    body = models.TextField()
    visibility = models.CharField(max_length=20, default="private")


class InstallmentPlan(TenantAwareModel):
    sale_order = models.OneToOneField(SaleOrder, on_delete=models.CASCADE, related_name="installment_plan")
    total_installments = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    minimum_first_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    final_payment_date = models.DateField(blank=True, null=True)


class InstallmentLine(TenantAwareModel):
    plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name="lines")
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    installment_status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("paid", "Paid"), ("partial", "Partial")], default="pending")


class ReturnOrder(TenantAwareModel):
    RETURN_TYPES = [("refund", "Refund"), ("exchange", "Exchange"), ("credit_note", "Credit Note")]
    STATUSES = [("draft", "Draft"), ("processed", "Processed"), ("cancelled", "Cancelled")]

    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="returns")
    customer = models.ForeignKey("customers.Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="returns")
    cashier = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_returns")
    return_type = models.CharField(max_length=20, choices=RETURN_TYPES, default="refund")
    return_status = models.CharField(max_length=20, choices=STATUSES, default="processed")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    note = models.TextField(blank=True)


class ReturnItem(TenantAwareModel):
    return_order = models.ForeignKey(ReturnOrder, on_delete=models.CASCADE, related_name="items")
    sale_item = models.ForeignKey(SaleItem, on_delete=models.PROTECT, related_name="return_items")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    condition = models.CharField(max_length=20, default="good")


class ExchangeOrderLink(TenantAwareModel):
    return_order = models.ForeignKey(ReturnOrder, on_delete=models.CASCADE, related_name="exchange_links")
    new_sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="exchange_links")
    difference_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
