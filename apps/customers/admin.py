from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.customers.models import (
    Customer,
    CustomerAccountHistory,
    CustomerAddress,
    CustomerCoupon,
    CustomerGroup,
    CustomerReward,
)


admin.site.register(CustomerGroup, TenantModelAdmin)


@admin.register(Customer)
class CustomerAdmin(TenantModelAdmin):
    list_display = (
        "id",
        "first_name",
        "last_name",
        "company",
        "branch",
        "group",
        "phone",
        "email",
        "owed_amount",
        "account_amount",
        "status",
    )
    search_fields = (
        "first_name",
        "last_name",
        "phone",
        "email",
    )
    list_filter = ("company", "branch", "group", "status")


admin.site.register(CustomerAddress, TenantModelAdmin)
admin.site.register(CustomerAccountHistory, TenantModelAdmin)
admin.site.register(CustomerCoupon, TenantModelAdmin)
admin.site.register(CustomerReward, TenantModelAdmin)
