from django.contrib import admin

from apps.audit.models import AuditLog
from apps.common.admin import TenantModelAdmin


admin.site.register(AuditLog, TenantModelAdmin)
