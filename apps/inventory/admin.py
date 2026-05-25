from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.inventory.models import (
    LowStockAlert,
    StockAdjustment,
    StockLedger,
    StockLot,
    StockTransfer,
    StockTransferItem,
)


admin.site.register(StockLot, TenantModelAdmin)
admin.site.register(StockLedger, TenantModelAdmin)
admin.site.register(StockAdjustment, TenantModelAdmin)
admin.site.register(StockTransfer, TenantModelAdmin)
admin.site.register(StockTransferItem, TenantModelAdmin)
admin.site.register(LowStockAlert, TenantModelAdmin)
