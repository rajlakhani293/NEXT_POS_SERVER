# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class CartDraft(TenantAwareModel):
    code = models.CharField(max_length=50)
    customer = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_cart_drafts",
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
        db_table = "cart_drafts"
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
        ("takeaway", "Takeaway"),
        ("delivery", "Delivery"),
    ]

    customer = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_sale_orders")
    cashier = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders")
    register = models.ForeignKey("registers.CashRegister", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders")
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders")
    code = models.CharField(max_length=50)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, default="takeaway")
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
        db_table = "orders"
        unique_together = [("branch", "code")]
        ordering = ["-id"]


class OrderPayment(TenantAwareModel):
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="payments", db_column="order_id")
    identifier = models.CharField(max_length=80, default="cash-payment")
    value = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "orders_payments"


class OrderStorage(TenantAwareModel):
    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_storage_entries")
    unit_quantity = models.ForeignKey("catalog.ProductUnitQuantity", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_storage_entries")
    unit = models.ForeignKey("catalog.Unit", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_storage_entries")
    quantity = models.IntegerField(null=True, blank=True)
    session_identifier = models.CharField(max_length=255)

    class Meta:
        db_table = "orders_storage"


class OrderAddress(TenantAwareModel):
    ADDRESS_TYPES = [("billing", "Billing"), ("shipping", "Shipping")]

    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="order_addresses", db_column="order_id")
    type = models.CharField(max_length=20, choices=ADDRESS_TYPES)
    first_name = models.CharField(max_length=120, blank=True, null=True)
    last_name = models.CharField(max_length=120, blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    address_1 = models.CharField(max_length=255, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    address_2 = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=120, blank=True, null=True)
    city = models.CharField(max_length=120, blank=True, null=True)
    pobox = models.CharField(max_length=50, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True, db_column="company")
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_addresses", db_column="author_id")

    class Meta:
        db_table = "orders_addresses"


class OrderTax(TenantAwareModel):
    tax = models.ForeignKey("catalog.Tax", on_delete=models.SET_NULL, null=True, blank=True, related_name="order_taxes")
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="taxes", db_column="order_id")
    rate = models.DecimalField(max_digits=12, decimal_places=5, default=0)
    tax_name = models.CharField(max_length=120, blank=True, null=True)
    tax_value = models.DecimalField(max_digits=14, decimal_places=5, default=0)

    class Meta:
        db_table = "orders_taxes"


class OrderSetting(TenantAwareModel):
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="settings", db_column="order_id")
    key = models.CharField(max_length=120)
    value = models.TextField(blank=True)

    class Meta:
        db_table = "orders_settings"


class SaleItem(TenantAwareModel):
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="sale_items")
    unit = models.ForeignKey("catalog.Unit", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_items")
    unit_quantity = models.ForeignKey("catalog.ProductUnitQuantity", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_items")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    item_status = models.CharField(max_length=20, default="sold")

    class Meta:
        db_table = "orders_products"


class InstallmentPlan(TenantAwareModel):
    sale_order = models.OneToOneField(SaleOrder, on_delete=models.CASCADE, related_name="installment_plan")
    total_installments = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    minimum_first_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    final_payment_date = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "orders_instalment_plans"


class InstallmentLine(TenantAwareModel):
    plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name="lines")
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    installment_status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("paid", "Paid"), ("partial", "Partial")], default="pending")

    class Meta:
        db_table = "orders_instalments"


class ReturnOrder(TenantAwareModel):
    RETURN_TYPES = [("refund", "Refund"), ("exchange", "Exchange"), ("credit_note", "Credit Note")]
    STATUSES = [("draft", "Draft"), ("processed", "Processed"), ("cancelled", "Cancelled")]

    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="returns")
    customer = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_returns")
    cashier = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_returns")
    return_type = models.CharField(max_length=20, choices=RETURN_TYPES, default="refund")
    return_status = models.CharField(max_length=20, choices=STATUSES, default="processed")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "orders_refunds"


class ReturnItem(TenantAwareModel):
    return_order = models.ForeignKey(ReturnOrder, on_delete=models.CASCADE, related_name="items")
    sale_item = models.ForeignKey(SaleItem, on_delete=models.PROTECT, related_name="return_items")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    condition = models.CharField(max_length=20, default="good")

    class Meta:
        db_table = "orders_products_refunds"


class ExchangeOrderLink(TenantAwareModel):
    return_order = models.ForeignKey(ReturnOrder, on_delete=models.CASCADE, related_name="exchange_links")
    new_sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="exchange_links")
    difference_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "orders_exchange_links"
