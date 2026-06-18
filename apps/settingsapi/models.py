# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel


class Option(TenantAwareModel):
    key = models.CharField(max_length=255)
    value = models.TextField(blank=True, null=True)
    expire_on = models.DateTimeField(blank=True, null=True)
    array = models.BooleanField(default=False)

    class Meta:
        db_table = "options"
        ordering = ["key", "id"]

    def __str__(self):
        return self.key


class Job(models.Model):
    STATUS_ACTIVE = 0
    STATUS_INACTIVE = 1
    STATUS_DELETED = 2

    user = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs")
    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE, related_name="jobs")
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, related_name="jobs")
    status = models.IntegerField(default=STATUS_ACTIVE, help_text="0: Active, 1: Inactive, 2: Deleted.")
    deleted_at = models.DateTimeField(blank=True, null=True)
    queue = models.CharField(max_length=255, db_index=True)
    payload = models.TextField()
    attempts = models.PositiveSmallIntegerField()
    reserved_at = models.PositiveIntegerField(blank=True, null=True)
    available_at = models.PositiveIntegerField()
    created_at = models.PositiveIntegerField()

    class Meta:
        db_table = "jobs"

    def __str__(self):
        return f"{self.queue}#{self.id}"


class FailedJob(models.Model):
    STATUS_ACTIVE = 0
    STATUS_INACTIVE = 1
    STATUS_DELETED = 2

    user = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="failed_jobs")
    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE, related_name="failed_jobs")
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, related_name="failed_jobs")
    status = models.IntegerField(default=STATUS_ACTIVE, help_text="0: Active, 1: Inactive, 2: Deleted.")
    deleted_at = models.DateTimeField(blank=True, null=True)
    connection = models.TextField()
    queue = models.TextField()
    payload = models.TextField()
    exception = models.TextField()
    failed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "failed_jobs"

    def __str__(self):
        return f"{self.queue} failed #{self.id}"
