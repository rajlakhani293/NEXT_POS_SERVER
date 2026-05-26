# type: ignore
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    STATUS_ACTIVE = 0
    STATUS_INACTIVE = 1
    STATUS_DELETED = 2
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Deactive"),
        (STATUS_DELETED, "Delete"),
    ]

    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        help_text="0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.",
    )
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    def activate(self):
        self.status = self.STATUS_ACTIVE
        self.deleted_at = None
        self.save(update_fields=["status", "deleted_at"])

    def deactivate(self):
        self.status = self.STATUS_INACTIVE
        self.save(update_fields=["status"])

    def soft_delete(self):
        self.status = self.STATUS_DELETED
        self.deleted_at = timezone.now()
        self.save(update_fields=["status", "deleted_at"])


class BaseModel(UUIDModel, TimeStampedModel, SoftDeleteModel):
    class Meta:
        abstract = True


class TenantAwareModel(BaseModel):
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
    )

    class Meta:
        abstract = True


class OwnedModel(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_%(class)ss",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_%(class)ss",
    )

    class Meta:
        abstract = True
