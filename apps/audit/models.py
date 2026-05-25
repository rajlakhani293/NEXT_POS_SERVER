from django.db import models

from apps.common.models import TenantAwareModel


class AuditLog(TenantAwareModel):
    actor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=120)
    entity_id = models.PositiveBigIntegerField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    payload = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True)
