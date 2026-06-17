# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


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
    cashier = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders", db_column="author_id")
    register = models.ForeignKey("registers.CashRegister", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders")
    shift = models.ForeignKey("registers.CashierShift", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders")
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, default="takeaway", db_column="type")
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUSES, default="unpaid")
    process_status = models.CharField(max_length=30, blank=True)
    delivery_status = models.CharField(max_length=30, blank=True)
    discount_type = models.CharField(max_length=30, blank=True, null=True)
    shipping_rate = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    shipping_type = models.CharField(max_length=30, blank=True, null=True)
    total_without_tax = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column="discount")
    discount_percentage = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    coupon_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column="total_coupons")
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column="shipping")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column="tax_value")
    products_tax_value = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    total_cogs = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    total_with_tax = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    tax_group = models.ForeignKey("catalog.TaxGroup", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_orders")
    tax_type = models.CharField(max_length=30, blank=True, null=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tendered_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_column="tendered")
    change_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_column="change")
    due_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_items = models.PositiveIntegerField(default=0)
    total_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    support_instalments = models.BooleanField(default=False)
    final_payment_date = models.DateTimeField(blank=True, null=True)
    total_instalments = models.PositiveIntegerField(default=0)
    note = models.TextField(blank=True)
    note_visibility = models.CharField(max_length=30, blank=True, null=True)
    voidance_reason = models.TextField(blank=True, null=True)
    driver = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="delivered_sale_orders", db_column="driver_id")

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
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="items", db_column="order_id")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="sale_items")
    unit = models.ForeignKey("catalog.Unit", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_items")
    unit_quantity = models.ForeignKey("catalog.ProductUnitQuantity", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_items", db_column="unit_quantity_id")
    product_category = models.ForeignKey("catalog.Category", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_items")
    procurement_product = models.ForeignKey("purchases.PurchaseItem", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_items")
    tax_group = models.ForeignKey("catalog.TaxGroup", on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_items")
    name = models.CharField(max_length=255, blank=True, null=True)
    unit_name = models.CharField(max_length=255, blank=True, null=True)
    mode = models.CharField(max_length=30, blank=True, null=True)
    product_type = models.CharField(max_length=30, blank=True, null=True)
    tax_type = models.CharField(max_length=30, blank=True, null=True)
    return_observations = models.TextField(blank=True, null=True)
    return_condition = models.CharField(max_length=255, blank=True, null=True)
    discount_type = models.CharField(max_length=30, blank=True, null=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column="discount")
    discount_percentage = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    price_gross = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    price_net = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    wholesale_tax_value = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    sale_tax_value = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column="tax_value")
    rate = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, db_column="total_price")
    total_price_gross = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    total_price_net = models.DecimalField(max_digits=14, decimal_places=5, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column="total_purchase_price")
    item_status = models.CharField(max_length=20, default="sold")

    class Meta:
        db_table = "orders_products"


class OrderInstalment(TenantAwareModel):
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="instalments", db_column="order_id")
    amount = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    paid = models.BooleanField(default=False)
    payment = models.ForeignKey(OrderPayment, on_delete=models.SET_NULL, null=True, blank=True, related_name="instalments", db_column="payment_id")
    date = models.DateTimeField()

    class Meta:
        db_table = "orders_instalments"


class ReturnOrder(TenantAwareModel):
    RETURN_TYPES = [("refund", "Refund"), ("exchange", "Exchange"), ("credit_note", "Credit Note")]
    STATUSES = [("draft", "Draft"), ("processed", "Processed"), ("cancelled", "Cancelled")]

    sale_order = models.ForeignKey(SaleOrder, on_delete=models.CASCADE, related_name="returns", db_column="order_id")
    customer = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_returns")
    cashier = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_returns", db_column="author_id")
    return_type = models.CharField(max_length=20, choices=RETURN_TYPES, default="refund")
    return_status = models.CharField(max_length=20, choices=STATUSES, default="processed")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=80, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "orders_refunds"


class ReturnItem(TenantAwareModel):
    return_order = models.ForeignKey(ReturnOrder, on_delete=models.CASCADE, related_name="items", db_column="order_refund_id")
    sale_order = models.ForeignKey(SaleOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="return_items", db_column="order_id")
    sale_item = models.ForeignKey(SaleItem, on_delete=models.PROTECT, related_name="return_items", db_column="order_product_id")
    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="return_items")
    unit = models.ForeignKey("catalog.Unit", on_delete=models.SET_NULL, null=True, blank=True, related_name="return_items")
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="authored_return_items", db_column="author_id")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2, db_column="total_price")
    condition = models.CharField(max_length=20, default="good")
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "orders_products_refunds"
