from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.inventory.models import (
    StockAdjustment,
    StockLedger,
)


admin.site.register(StockLedger, TenantModelAdmin)
admin.site.register(StockAdjustment, TenantModelAdmin)
