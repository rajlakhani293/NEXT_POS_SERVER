from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.registers.models import CashierShift, CashRegister, CashRegisterEntry


admin.site.register(CashRegister, TenantModelAdmin)
admin.site.register(CashierShift, TenantModelAdmin)
admin.site.register(CashRegisterEntry, TenantModelAdmin)
