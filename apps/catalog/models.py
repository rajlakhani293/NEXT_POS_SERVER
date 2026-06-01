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
    ]

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
