from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.registers.models import CashRegister, CashRegisterEntry


admin.site.register(CashRegister, TenantModelAdmin)
admin.site.register(CashRegisterEntry, TenantModelAdmin)
