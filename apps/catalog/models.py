# type: ignore
from django.db import models

from apps.common.models import TenantAwareModel


class Category(TenantAwareModel):
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=150)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(TenantAwareModel):
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=150)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class UnitGroup(TenantAwareModel):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]


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
    code = models.SlugField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]


class Tax(TenantAwareModel):
    tax_group = models.ForeignKey(TaxGroup, on_delete=models.CASCADE, related_name="taxes")
    name = models.CharField(max_length=120)
    rate = models.DecimalField(max_digits=8, decimal_places=2)
    is_inclusive = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]


class Product(TenantAwareModel):
    PRODUCT_TYPES = [
        ("stock", "Stock"),
        ("service", "Service"),
        ("bundle", "Bundle"),
    ]

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    tax_group = models.ForeignKey(TaxGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    unit_group = models.ForeignKey(UnitGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    sku = models.CharField(max_length=120)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES, default="stock")
    description = models.TextField(blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mrp = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    min_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    track_stock = models.BooleanField(default=True)
    allow_decimal_qty = models.BooleanField(default=False)

    class Meta:
        unique_together = [("branch", "sku"), ("branch", "slug")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductVariant(TenantAwareModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name="variants")
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=120)
    barcode = models.CharField(max_length=120, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mrp = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    class Meta:
        unique_together = [("branch", "sku"), ("branch", "barcode")]
        ordering = ["product__name", "name"]

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class ProductBarcode(TenantAwareModel):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="barcodes")
    code = models.CharField(max_length=120)
    is_primary = models.BooleanField(default=False)

    class Meta:
        unique_together = [("branch", "code")]


class ProductImage(TenantAwareModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.URLField()
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)


class ProductBundleItem(TenantAwareModel):
    bundle = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="bundle_items")
    item = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="used_in_bundles")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)

    class Meta:
        unique_together = [("bundle", "item")]
