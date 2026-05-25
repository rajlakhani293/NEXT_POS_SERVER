from django.db import models

from apps.common.models import TenantAwareModel


class Coupon(TenantAwareModel):
    DISCOUNT_TYPES = [
        ("flat", "Flat"),
        ("percentage", "Percentage"),
    ]

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=120)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2)
    max_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    minimum_cart_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    usage_limit = models.PositiveIntegerField(default=0)
    per_customer_limit = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    applies_to_all_products = models.BooleanField(default=True)

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
    discount_type = models.CharField(max_length=20)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
