from django.contrib import admin

from apps.common.admin import SmartModelAdmin
from apps.organizations.models import Branch, Company


@admin.register(Company)
class CompanyAdmin(SmartModelAdmin):
    pass


@admin.register(Branch)
class BranchAdmin(SmartModelAdmin):
    list_display = (
        "id",
        "name",
        "company",
        "code",
        "city",
        "state",
        "phone",
        "is_head_office",
        "status",
    )
    search_fields = ("name", "code", "city", "state", "phone", "company__name")
    list_filter = ("company", "is_head_office", "status", "country")
