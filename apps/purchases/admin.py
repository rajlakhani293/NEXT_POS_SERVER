from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.purchases.models import PurchaseItem, PurchaseOrder, Supplier


admin.site.register(Supplier, TenantModelAdmin)
admin.site.register(PurchaseOrder, TenantModelAdmin)
admin.site.register(PurchaseItem, TenantModelAdmin)
