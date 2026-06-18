# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class Provider(TenantAwareModel):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    address_1 = models.CharField(max_length=255, blank=True, null=True)
    address_2 = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    amount_due = models.FloatField(default=0)
    amount_paid = models.FloatField(default=0)
    uuid = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "providers"
        ordering = ["first_name"]


class Procurement(TenantAwareModel):
    name = models.CharField(max_length=255)
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name="procurements")
    value = models.FloatField(default=0)
    cost = models.FloatField(default=0)
    tax_value = models.FloatField(default=0)
    invoice_reference = models.CharField(max_length=255, blank=True, null=True)
    automatic_approval = models.BooleanField(default=False, null=True)
    delivery_time = models.DateTimeField(blank=True, null=True)
    invoice_date = models.DateTimeField(blank=True, null=True)
    payment_status = models.CharField(max_length=120, default="unpaid")
    delivery_status = models.CharField(max_length=120, default="pending")
    total_items = models.IntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    uuid = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "procurements"
        ordering = ["-id"]


class ProcurementsProduct(TenantAwareModel):
    name = models.CharField(max_length=255)
    gross_purchase_price = models.FloatField(default=0)
    net_purchase_price = models.FloatField(default=0)
    procurement = models.ForeignKey(Procurement, on_delete=models.CASCADE, related_name="products")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="purchase_items")
    purchase_price = models.FloatField(default=0)
    quantity = models.FloatField()
    available_quantity = models.FloatField()
    tax_group = models.ForeignKey("catalog.TaxGroup", on_delete=models.SET_NULL, null=True, blank=True, related_name="procurement_products")
    barcode = models.CharField(max_length=255, blank=True, null=True)
    expiration_date = models.DateTimeField(blank=True, null=True)
    tax_type = models.CharField(max_length=120, default="exclusive")
    tax_value = models.FloatField(default=0)
    total_purchase_price = models.FloatField(default=0)
    unit = models.ForeignKey("catalog.Unit", on_delete=models.PROTECT, related_name="procurement_products")
    convert_unit = models.ForeignKey("catalog.Unit", on_delete=models.SET_NULL, null=True, blank=True, related_name="converted_procurement_products")
    uuid = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "procurements_products"
