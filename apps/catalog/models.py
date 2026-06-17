# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class ScaleRange(TenantAwareModel):
    name = models.CharField(max_length=255)
    range_start = models.IntegerField(default=0)
    range_end = models.IntegerField(default=0)
    next_scale_plu = models.IntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "scale_ranges"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(TenantAwareModel):
    name = models.CharField(max_length=150)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    media_id = models.IntegerField(default=0)
    preview_url = models.URLField(blank=True, null=True)
    displays_on_pos = models.BooleanField(default=True)
    scale_range = models.ForeignKey(ScaleRange, on_delete=models.SET_NULL, null=True, blank=True, related_name="categories")
    total_items = models.IntegerField(default=0)
    position = models.IntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "products_categories"
        ordering = ["position", "name"]

    def __str__(self):
        return self.name


class UnitGroup(TenantAwareModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "units_groups"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Unit(TenantAwareModel):
    name = models.CharField(max_length=120)
    identifier = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    group = models.ForeignKey(UnitGroup, on_delete=models.CASCADE, related_name="units")
    value = models.FloatField(default=1)
    preview_url = models.URLField(blank=True, null=True)
    base_unit = models.BooleanField(default=False)

    class Meta:
        db_table = "units"
        ordering = ["name"]
        unique_together = [("branch", "identifier")]

    def __str__(self):
        return self.name


class TaxGroup(TenantAwareModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "taxes_groups"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tax(TenantAwareModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    rate = models.FloatField(default=0)
    tax_group = models.ForeignKey(TaxGroup, on_delete=models.CASCADE, related_name="taxes")

    class Meta:
        db_table = "taxes"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(TenantAwareModel):
    PRODUCT_TYPES = [
        ("product", "Product"),
        ("variation", "Variation"),
        ("variable", "Variable"),
    ]
    ITEM_TYPES = [
        ("tangible", "Tangible"),
        ("intangible", "Intangible"),
    ]
    STOCK_MANAGEMENT = [
        ("enabled", "Enabled"),
        ("disabled", "Disabled"),
    ]
    EXPIRATION_ACTIONS = [
        ("prevent_sales", "Prevent Sales"),
        ("allow_sales", "Allow Sales"),
    ]

    name = models.CharField(max_length=255)
    tax_type = models.CharField(max_length=120, blank=True, null=True)
    tax_group = models.ForeignKey(TaxGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    tax_value = models.FloatField(default=0)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default="product")
    type = models.CharField(max_length=20, choices=ITEM_TYPES, default="tangible")
    accurate_tracking = models.BooleanField(default=False)
    auto_cogs = models.BooleanField(default=True)
    stock_management = models.CharField(max_length=20, choices=STOCK_MANAGEMENT, default="enabled")
    barcode = models.CharField(max_length=120, blank=True, null=True)
    barcode_type = models.CharField(max_length=120, blank=True, null=True)
    sku = models.CharField(max_length=120, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    thumbnail_id = models.IntegerField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="variations")
    unit_group = models.ForeignKey(UnitGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    on_expiration = models.CharField(max_length=40, choices=EXPIRATION_ACTIONS, default="prevent_sales")
    expires = models.BooleanField(default=False)
    searchable = models.BooleanField(default=True)
    position = models.IntegerField(default=0)
    pinned = models.BooleanField(default=False)

    class Meta:
        db_table = "products"
        ordering = ["position", "name"]
        unique_together = [("branch", "sku"), ("branch", "barcode")]

    def __str__(self):
        return self.name


class ProductGallery(TenantAwareModel):
    name = models.CharField(max_length=255, blank=True, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="gallery")
    media_id = models.IntegerField(blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    order = models.IntegerField(default=0)
    featured = models.BooleanField(default=False)

    class Meta:
        db_table = "products_galleries"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name or self.url or f"Product image {self.id}"


class ProductUnitQuantity(TenantAwareModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="unit_quantities")
    type = models.CharField(max_length=120, default="product")
    preview_url = models.URLField(blank=True, null=True)
    expiration_date = models.DateTimeField(blank=True, null=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="product_quantities")
    barcode = models.CharField(max_length=120, blank=True, null=True)
    scale_plu = models.CharField(max_length=10, blank=True, null=True)
    is_weighable = models.BooleanField(default=False)
    quantity = models.FloatField(default=0)
    low_quantity = models.FloatField(default=0)
    stock_alert_enabled = models.BooleanField(default=False)
    sale_price = models.FloatField(default=0)
    sale_price_edit = models.FloatField(default=0)
    sale_price_net = models.FloatField(default=0)
    sale_price_gross = models.FloatField(default=0)
    sale_price_tax = models.FloatField(default=0)
    wholesale_price = models.FloatField(default=0)
    wholesale_price_edit = models.FloatField(default=0)
    wholesale_price_gross = models.FloatField(default=0)
    wholesale_price_net = models.FloatField(default=0)
    wholesale_price_tax = models.FloatField(default=0)
    custom_price = models.FloatField(default=0)
    custom_price_edit = models.FloatField(default=0)
    custom_price_gross = models.FloatField(default=0)
    custom_price_net = models.FloatField(default=0)
    custom_price_tax = models.FloatField(default=0)
    visible = models.BooleanField(default=True)
    convert_unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name="converted_product_quantities")
    cogs = models.FloatField(default=0)

    class Meta:
        db_table = "products_unit_quantities"
        ordering = ["id"]
        unique_together = [("product", "unit")]

    def __str__(self):
        return f"{self.product} - {self.unit}"


class ProductTax(TenantAwareModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="product_taxes")
    unit_quantity = models.ForeignKey(ProductUnitQuantity, on_delete=models.CASCADE, related_name="taxes")
    tax_id = models.CharField(max_length=120)
    name = models.CharField(max_length=255)
    rate = models.FloatField(default=0)
    value = models.FloatField(default=0)

    class Meta:
        db_table = "products_taxes"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductHistory(TenantAwareModel):
    ACTION_STOCKED = "procured"
    ACTION_DELETED = "deleted"
    ACTION_TRANSFER_OUT = "outgoing-transfer"
    ACTION_TRANSFER_IN = "incoming-transfer"
    ACTION_TRANSFER_REJECTED = "transfer-rejected"
    ACTION_TRANSFER_CANCELED = "transfer-canceled"
    ACTION_REMOVED = "removed"
    ACTION_ADDED = "added"
    ACTION_SOLD = "sold"
    ACTION_RETURNED = "returned"
    ACTION_DEFECTIVE = "defective"
    ACTION_LOST = "lost"
    ACTION_VOID_RETURN = "void-return"
    ACTION_ADJUSTMENT_RETURN = "return-adjustment"
    ACTION_ADJUSTMENT_SALE = "sale-adjustment"
    ACTION_CONVERT_OUT = "convert-out"
    ACTION_CONVERT_IN = "convert-in"
    ACTION_SET = "set"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="histories")
    procurement_id = models.IntegerField(blank=True, null=True)
    procurement_product_id = models.IntegerField(blank=True, null=True)
    order_id = models.IntegerField(blank=True, null=True)
    order_product_id = models.IntegerField(blank=True, null=True)
    operation_type = models.CharField(max_length=120)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="product_histories")
    before_quantity = models.FloatField(blank=True, null=True)
    quantity = models.FloatField(default=0)
    after_quantity = models.FloatField(blank=True, null=True)
    unit_price = models.FloatField(default=0)
    total_price = models.FloatField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "products_histories"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product} - {self.operation_type}"


class ProductHistoryCombined(TenantAwareModel):
    name = models.CharField(max_length=255)
    date = models.DateField()
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="combined_histories")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="combined_product_histories")
    initial_quantity = models.FloatField(default=0)
    sold_quantity = models.FloatField(default=0)
    procured_quantity = models.FloatField(default=0)
    defective_quantity = models.FloatField(default=0)
    final_quantity = models.FloatField(default=0)

    class Meta:
        db_table = "products_histories_combined"
        ordering = ["-date", "name"]

    def __str__(self):
        return self.name


class ProductSubItem(TenantAwareModel):
    parent = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="subitems")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="as_subitem")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="subitems")
    unit_quantity = models.ForeignKey(ProductUnitQuantity, on_delete=models.PROTECT, related_name="subitems")
    sale_price = models.FloatField(default=0)
    quantity = models.FloatField(default=0)
    total_price = models.FloatField(default=0)

    class Meta:
        db_table = "products_subitems"
        ordering = ["id"]

    def __str__(self):
        return f"{self.parent} -> {self.product}"


class ProductMeta(TenantAwareModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="metas")
    key = models.CharField(max_length=255)
    value = models.TextField(blank=True)

    class Meta:
        db_table = "products_metas"
        ordering = ["key"]
        unique_together = [("product", "key")]

    def __str__(self):
        return self.key
