# type:ignore
from django.db import models
from apps.common.models import TenantAwareModel


class Media(TenantAwareModel):
    name = models.CharField(max_length=255, unique=True)
    extension = models.CharField(max_length=50)
    slug = models.CharField(max_length=255)

    class Meta:
        db_table = "medias"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name
