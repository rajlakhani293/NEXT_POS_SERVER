# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel

class Coupon(TenantAwareModel):
    DISCOUNT_TYPES = [
        ("flat_discount", "Flat Discount"),
        ("percentage_discount", "Percentage Discount"),
    ]

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=120)
    type = models.CharField(max_length=30, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2)
    valid_until = models.DateTimeField(blank=True, null=True)
    minimum_cart_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maximum_cart_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valid_hours_start = models.TimeField(blank=True, null=True)
    valid_hours_end = models.TimeField(blank=True, null=True)
    limit_usage = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "coupons"
        unique_together = [("branch", "code")]
        ordering = ["name"]


class CouponProduct(TenantAwareModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="coupon_products")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="coupon_links")

    class Meta:
        db_table = "coupons_products"
        unique_together = [("coupon", "product")]


class CouponCategory(TenantAwareModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="coupon_categories")
    category = models.ForeignKey("catalog.Category", on_delete=models.CASCADE, related_name="coupon_links")

    class Meta:
        db_table = "coupons_categories"
        unique_together = [("coupon", "category")]


class CouponCustomer(TenantAwareModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="coupon_customers")
    customer = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="coupon_links")

    class Meta:
        db_table = "coupons_customers"
        unique_together = [("coupon", "customer")]


class CouponCustomerGroup(TenantAwareModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="coupon_customer_groups")
    customer_group = models.ForeignKey("customers.CustomerGroup", on_delete=models.CASCADE, related_name="coupon_links")

    class Meta:
        db_table = "coupons_customers_groups"
        unique_together = [("coupon", "customer_group")]


class OrdersCoupon(TenantAwareModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=150)
    customer_coupon_id = models.PositiveIntegerField(null=True, blank=True)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="applied_orders")
    sale_order = models.ForeignKey("sales.Order", on_delete=models.CASCADE, related_name="applied_coupons", db_column="order_id")
    type = models.CharField(max_length=30)
    discount_value = models.DecimalField(max_digits=18, decimal_places=5)
    minimum_cart_value = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    maximum_cart_value = models.DecimalField(max_digits=18, decimal_places=5, default=0)
    limit_usage = models.PositiveIntegerField(default=0)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=5, default=0, db_column="value")
    counted = models.BooleanField(default=False)

    class Meta:
        db_table = "orders_coupons"
