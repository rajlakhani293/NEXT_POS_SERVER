from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.purchases.models import ProcurementsProduct, Procurement, Provider


admin.site.register(Provider, TenantModelAdmin)
admin.site.register(Procurement, TenantModelAdmin)
admin.site.register(ProcurementsProduct, TenantModelAdmin)
