from django.db import models

from apps.common.models import TenantAwareModel


class Media(TenantAwareModel):
    file_name = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255, blank=True)
    file_url = models.URLField(max_length=600)
    file_path = models.CharField(max_length=500, blank=True)
    mime_type = models.CharField(max_length=120, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    folder = models.CharField(max_length=120, default="general")
    alt_text = models.CharField(max_length=255, blank=True)
    entity_type = models.CharField(max_length=80, blank=True)
    entity_id = models.PositiveBigIntegerField(blank=True, null=True)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="uploaded_media",
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.original_name or self.file_name
