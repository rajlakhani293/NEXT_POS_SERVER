# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class RewardSystem(TenantAwareModel):
    name = models.CharField(max_length=150)
    coupon = models.ForeignKey(
        "promotions.Coupon",
        on_delete=models.PROTECT,
        related_name="reward_systems",
    )
    target = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "rewards_system"
        ordering = ["name"]


class RewardRule(TenantAwareModel):
    reward_system = models.ForeignKey(RewardSystem, on_delete=models.CASCADE, related_name="rules", db_column="reward_id")
    from_amount = models.DecimalField(max_digits=18, decimal_places=5, default=0, db_column="from")
    to_amount = models.DecimalField(max_digits=18, decimal_places=5, default=0, db_column="to")
    reward = models.DecimalField(max_digits=18, decimal_places=5, default=0)

    class Meta:
        db_table = "rewards_system_rules"
        ordering = ["from_amount"]


class RewardRedemption(TenantAwareModel):
    customer = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="reward_redemptions")
    reward_system = models.ForeignKey(RewardSystem, on_delete=models.PROTECT, related_name="redemptions")
    customer_coupon = models.ForeignKey(
        "customers.CustomerCoupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reward_redemptions",
    )
    points_redeemed = models.PositiveIntegerField(default=0)
    note = models.TextField(blank=True)
