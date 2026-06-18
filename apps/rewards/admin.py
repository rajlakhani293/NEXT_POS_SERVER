from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.rewards.models import (
    RewardRule,
    RewardSystem,
)


admin.site.register(RewardSystem, TenantModelAdmin)
admin.site.register(RewardRule, TenantModelAdmin)
