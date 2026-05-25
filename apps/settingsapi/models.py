from django.db import models

from apps.common.models import TenantAwareModel


class Setting(TenantAwareModel):
    key = models.CharField(max_length=150)
    value = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [("branch", "key")]
