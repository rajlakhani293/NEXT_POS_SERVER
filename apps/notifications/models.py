# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class Notification(TenantAwareModel):
    identifier = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    description = models.TextField()
    url = models.CharField(max_length=255, default="#")
    source = models.CharField(max_length=255, default="system")
    dismissable = models.BooleanField(default=True)
    actions = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title
