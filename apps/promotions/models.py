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
    minimum_cart_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maximum_cart_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valid_until = models.DateTimeField(blank=True, null=True)
    valid_hours_start = models.TimeField(blank=True, null=True)
    valid_hours_end = models.TimeField(blank=True, null=True)
    limit_usage = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["name"]


class CouponProduct(TenantAwareModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="coupon_products")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="coupon_links")

    class Meta:
        unique_together = [("coupon", "product")]


class CouponCategory(TenantAwareModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="coupon_categories")
    category = models.ForeignKey("catalog.Category", on_delete=models.CASCADE, related_name="coupon_links")

    class Meta:
        unique_together = [("coupon", "category")]


class CouponCustomer(TenantAwareModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="coupon_customers")
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="coupon_links")

    class Meta:
        unique_together = [("coupon", "customer")]


class CouponCustomerGroup(TenantAwareModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="coupon_customer_groups")
    customer_group = models.ForeignKey("customers.CustomerGroup", on_delete=models.CASCADE, related_name="coupon_links")

    class Meta:
        unique_together = [("coupon", "customer_group")]


class CustomerCoupon(TenantAwareModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="issued_coupons")
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="coupons")
    code = models.CharField(max_length=150)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    usage_count = models.PositiveIntegerField(default=0)
    is_redeemed = models.BooleanField(default=False)
    redeemed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = [("customer", "code")]


class AppliedCoupon(TenantAwareModel):
    sale_order = models.ForeignKey("sales.SaleOrder", on_delete=models.CASCADE, related_name="applied_coupons")
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="applied_orders")
    customer_coupon = models.ForeignKey(
        CustomerCoupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_orders",
    )
    code = models.CharField(max_length=150)
    type = models.CharField(max_length=30)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
