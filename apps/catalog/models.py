# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class Category(TenantAwareModel):
    name = models.CharField(max_length=150)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(TenantAwareModel):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UnitGroup(TenantAwareModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Unit(TenantAwareModel):
    unit_group = models.ForeignKey(UnitGroup, on_delete=models.CASCADE, related_name="units")
    name = models.CharField(max_length=120)
    short_name = models.CharField(max_length=20)
    factor = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    is_base_unit = models.BooleanField(default=False)

    class Meta:
        unique_together = [("unit_group", "name")]

    def __str__(self):
        return self.short_name


class TaxGroup(TenantAwareModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Tax(TenantAwareModel):
    tax_group = models.ForeignKey(TaxGroup, on_delete=models.CASCADE, related_name="taxes")
    name = models.CharField(max_length=120)
    rate = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ["name"]


class Product(TenantAwareModel):
    PRODUCT_TYPES = [
        ("stock", "Stock"),
        ("service", "Service"),
        ("variation", "Variation"),
    ]

    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="variations")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    tax_group = models.ForeignKey(TaxGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=120, blank=True, null=True)
    barcode = models.CharField(max_length=120, blank=True, null=True)
    image = models.URLField(blank=True)
    weight = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default="stock")
    description = models.TextField(blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mrp = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_tax_inclusive = models.BooleanField(default=False)
    current_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    opening_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    min_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    max_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    track_stock = models.BooleanField(default=True)
    allow_decimal_qty = models.BooleanField(default=False)
    expiry_tracking_enabled = models.BooleanField(default=False)

    class Meta:
        unique_together = [("branch", "sku"), ("branch", "barcode")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductGallery(TenantAwareModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="gallery")
    image = models.URLField()
    alt_text = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class ProductSubItem(TenantAwareModel):
    parent_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sub_items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="used_in_bundles")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name="bundle_sub_items")

    class Meta:
        unique_together = [("parent_product", "product")]


class ProductUnitQuantity(TenantAwareModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="unit_quantities")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="product_quantities")
    convert_unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name="converted_product_quantities")
    barcode = models.CharField(max_length=120, blank=True, null=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_default = models.BooleanField(default=False)
    scale_plu = models.CharField(max_length=80, blank=True)

    class Meta:
        unique_together = [("product", "unit")]


class ProductTax(TenantAwareModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_taxes")
    tax = models.ForeignKey(Tax, on_delete=models.PROTECT, related_name="product_taxes")
    tax_rate = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_inclusive = models.BooleanField(default=False)

    class Meta:
        unique_together = [("product", "tax")]


class ScaleRange(TenantAwareModel):
    name = models.CharField(max_length=150)
    prefix = models.CharField(max_length=20, blank=True)
    start_range = models.PositiveIntegerField(default=0)
    end_range = models.PositiveIntegerField(default=0)
    value_type = models.CharField(max_length=30, choices=[("price", "Price"), ("weight", "Weight"), ("quantity", "Quantity")], default="weight")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]


class ProductHistory(TenantAwareModel):
    HISTORY_TYPES = [
        ("purchase", "Purchase"),
        ("sale", "Sale"),
        ("return", "Return"),
        ("adjustment", "Adjustment"),
        ("opening_stock", "Opening Stock"),
        ("manual", "Manual"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="histories")
    history_type = models.CharField(max_length=30, choices=HISTORY_TYPES, default="manual")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    before_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    after_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reference_type = models.CharField(max_length=60, blank=True)
    reference_id = models.PositiveBigIntegerField(blank=True, null=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class ProductHistoryCombined(TenantAwareModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="combined_histories")
    entry_type = models.CharField(max_length=60)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    balance_after = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    source_type = models.CharField(max_length=60, blank=True)
    source_id = models.PositiveBigIntegerField(blank=True, null=True)
    payload = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
