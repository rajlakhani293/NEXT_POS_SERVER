from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.sales.models import (
    OrderAddress,
    OrderInstalment,
    OrderPayment,
    OrderSetting,
    OrderStorage,
    OrderTax,
    OrdersProductsRefund,
    OrdersRefund,
    OrdersProduct,
    Order,
)


admin.site.register(Order, TenantModelAdmin)
admin.site.register(OrdersProduct, TenantModelAdmin)
admin.site.register(OrderPayment, TenantModelAdmin)
admin.site.register(OrderStorage, TenantModelAdmin)
admin.site.register(OrderAddress, TenantModelAdmin)
admin.site.register(OrderTax, TenantModelAdmin)
admin.site.register(OrderSetting, TenantModelAdmin)
admin.site.register(OrderInstalment, TenantModelAdmin)
admin.site.register(OrdersRefund, TenantModelAdmin)
admin.site.register(OrdersProductsRefund, TenantModelAdmin)
