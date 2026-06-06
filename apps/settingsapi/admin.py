from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.settingsapi.models import BusinessSetting, Setting


admin.site.register(Setting, TenantModelAdmin)
admin.site.register(BusinessSetting, TenantModelAdmin)
