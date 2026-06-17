from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.sales.models import (
    OrderAddress,
    OrderInstalment,
    OrderPayment,
    OrderSetting,
    OrderStorage,
    OrderTax,
    ReturnItem,
    ReturnOrder,
    SaleItem,
    SaleOrder,
)


admin.site.register(SaleOrder, TenantModelAdmin)
admin.site.register(SaleItem, TenantModelAdmin)
admin.site.register(OrderPayment, TenantModelAdmin)
admin.site.register(OrderStorage, TenantModelAdmin)
admin.site.register(OrderAddress, TenantModelAdmin)
admin.site.register(OrderTax, TenantModelAdmin)
admin.site.register(OrderSetting, TenantModelAdmin)
admin.site.register(OrderInstalment, TenantModelAdmin)
admin.site.register(ReturnOrder, TenantModelAdmin)
admin.site.register(ReturnItem, TenantModelAdmin)
