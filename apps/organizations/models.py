# type: ignore
from django.db import models
from apps.common.models import BaseModel

class Company(BaseModel):
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    code = models.SlugField(max_length=100, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    gst_number = models.CharField(max_length=50, blank=True)
    city_name = models.CharField(max_length=120, blank=True)
    state = models.ForeignKey("StateMaster", on_delete=models.SET_NULL, null=True, blank=True, related_name="companies")
    address = models.TextField(blank=True)
    logo = models.URLField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StateMaster(BaseModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Branch(BaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="branches",
    )
    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=100)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.ForeignKey(StateMaster, on_delete=models.SET_NULL, null=True, blank=True, related_name="branches")
    postal_code = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_head_office = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        unique_together = [("company", "code")]

    def __str__(self):
        return f"{self.company.name} - {self.name}"
