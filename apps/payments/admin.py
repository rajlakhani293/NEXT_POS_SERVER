from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.payments.models import PaymentType, RefundPayment, SalePayment


@admin.register(PaymentType)
class PaymentTypeAdmin(TenantModelAdmin):
    list_display = ("label", "identifier", "branch", "is_system", "is_enabled", "sort_order", "status")
    list_filter = ("is_system", "is_enabled", "status")
    search_fields = ("label", "identifier")

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_system and "identifier" not in readonly_fields:
            readonly_fields.append("identifier")
        return readonly_fields


admin.site.register(SalePayment, TenantModelAdmin)
admin.site.register(RefundPayment, TenantModelAdmin)
