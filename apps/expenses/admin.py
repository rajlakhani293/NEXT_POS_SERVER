from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.expenses.models import ExpenseCategory, ExpenseEntry


admin.site.register(ExpenseCategory, TenantModelAdmin)
admin.site.register(ExpenseEntry, TenantModelAdmin)
