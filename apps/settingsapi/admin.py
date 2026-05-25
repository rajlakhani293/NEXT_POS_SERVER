from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.settingsapi.models import Setting


admin.site.register(Setting, TenantModelAdmin)
