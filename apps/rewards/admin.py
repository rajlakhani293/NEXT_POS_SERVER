from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.rewards.models import (
    RewardsSystemRule,
    RewardSystem,
)


admin.site.register(RewardSystem, TenantModelAdmin)
admin.site.register(RewardsSystemRule, TenantModelAdmin)
