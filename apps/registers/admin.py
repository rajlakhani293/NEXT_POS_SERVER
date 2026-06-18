from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.registers.models import Register, RegistersHistory


admin.site.register(Register, TenantModelAdmin)
admin.site.register(RegistersHistory, TenantModelAdmin)
