from django.db import models

from apps.common.models import TenantAwareModel


class RewardSystem(TenantAwareModel):
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=150)
    coupon = models.ForeignKey(
        "promotions.Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reward_systems",
    )
    target_points = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "code")]
        ordering = ["name"]


class RewardRule(TenantAwareModel):
    reward_system = models.ForeignKey(RewardSystem, on_delete=models.CASCADE, related_name="rules")
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    points = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["min_amount"]


class CustomerRewardBalance(TenantAwareModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="reward_balances")
    reward_system = models.ForeignKey(RewardSystem, on_delete=models.CASCADE, related_name="customer_balances")
    points = models.PositiveIntegerField(default=0)
    lifetime_points = models.PositiveIntegerField(default=0)
    target_points = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("customer", "reward_system")]


class RewardRedemption(TenantAwareModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="reward_redemptions")
    reward_system = models.ForeignKey(RewardSystem, on_delete=models.PROTECT, related_name="redemptions")
    customer_coupon = models.ForeignKey(
        "promotions.CustomerCoupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reward_redemptions",
    )
    points_redeemed = models.PositiveIntegerField(default=0)
    note = models.TextField(blank=True)
