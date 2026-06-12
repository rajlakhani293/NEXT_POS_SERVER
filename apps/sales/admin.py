from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.sales.models import (
    CartDraft,
    ExchangeOrderLink,
    InstallmentLine,
    InstallmentPlan,
    ReturnItem,
    ReturnOrder,
    SaleItem,
    SaleOrder,
)


admin.site.register(CartDraft, TenantModelAdmin)
admin.site.register(SaleOrder, TenantModelAdmin)
admin.site.register(SaleItem, TenantModelAdmin)
admin.site.register(InstallmentPlan, TenantModelAdmin)
admin.site.register(InstallmentLine, TenantModelAdmin)
admin.site.register(ReturnOrder, TenantModelAdmin)
admin.site.register(ReturnItem, TenantModelAdmin)
admin.site.register(ExchangeOrderLink, TenantModelAdmin)
