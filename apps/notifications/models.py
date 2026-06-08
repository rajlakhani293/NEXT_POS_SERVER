from django.db import models

from apps.common.models import TenantAwareModel


class Notification(TenantAwareModel):
    NOTIFICATION_TYPES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("success", "Success"),
        ("error", "Error"),
    ]
    SOURCE_TYPES = [
        ("system", "System"),
        ("inventory", "Inventory"),
        ("customer", "Customer"),
        ("supplier", "Supplier"),
        ("cash_register", "Cash Register"),
        ("reward", "Reward"),
        ("coupon", "Coupon"),
        ("accounting", "Accounting"),
    ]

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        blank=True,
        null=True,
    )
    title = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default="info")
    source_type = models.CharField(max_length=40, choices=SOURCE_TYPES, default="system")
    source_id = models.PositiveBigIntegerField(blank=True, null=True)
    action_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title
