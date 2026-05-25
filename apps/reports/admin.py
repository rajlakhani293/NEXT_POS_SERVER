from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.reports.models import DayClosing, SalesSummarySnapshot


admin.site.register(DayClosing, TenantModelAdmin)
admin.site.register(SalesSummarySnapshot, TenantModelAdmin)
