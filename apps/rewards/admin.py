from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.rewards.models import (
    CustomerRewardBalance,
    RewardRedemption,
    RewardRule,
    RewardSystem,
)


admin.site.register(RewardSystem, TenantModelAdmin)
admin.site.register(RewardRule, TenantModelAdmin)
admin.site.register(CustomerRewardBalance, TenantModelAdmin)
admin.site.register(RewardRedemption, TenantModelAdmin)
