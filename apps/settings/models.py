# type: ignore
from django.db import models
from apps.common.models import TenantAwareModel
from apps.accounts.models import User
from apps.organizations.models import Company, Branch

PAYMENT_TYPES = [
    ("cash-payment", "Cash"),
    ("bank-payment", "Bank Payment"),
    ("account-payment", "Customer Account"),
]


def paymentTypeOptions():
    return [{"value": value, "label": label} for value, label in PAYMENT_TYPES]


def paymentTypeValues():
    return [value for value, _label in PAYMENT_TYPES]


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
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="jobs")
    status = models.IntegerField(default=0, help_text="0: Active, 1: Inactive, 2: Deleted.")
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
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="failed_jobs")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="failed_jobs")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="failed_jobs")
    status = models.IntegerField(default=0, help_text="0: Active, 1: Inactive, 2: Deleted.")
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


class Media(TenantAwareModel):
    name = models.CharField(max_length=255, unique=True)
    extension = models.CharField(max_length=50)
    slug = models.CharField(max_length=255)

    class Meta:
        db_table = "medias"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name


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


class PaymentType(TenantAwareModel):
    label = models.CharField(max_length=120)
    identifier = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    readonly = models.BooleanField(default=False)
    priority = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "payments_types"
        unique_together = [("branch", "identifier"), ("branch", "label")]
        ordering = ["priority", "label"]

    def __str__(self):
        return self.label
