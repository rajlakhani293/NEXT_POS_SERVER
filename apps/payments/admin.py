# type: ignore
from django.contrib import admin
from apps.common.admin import TenantModelAdmin
from apps.payments.models import PaymentType


@admin.register(PaymentType)
class PaymentTypeAdmin(TenantModelAdmin):
    list_display = ("label", "identifier", "branch", "readonly", "sort_order", "status")
    list_filter = ("readonly", "status")
    search_fields = ("label", "identifier")

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.readonly and "identifier" not in readonly_fields:
            readonly_fields.append("identifier")
        return readonly_fields
