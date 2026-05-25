from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.customers.models import (
    Customer,
    CustomerAddress,
    CustomerCreditLedger,
    CustomerGroup,
    CustomerWalletTransaction,
)


admin.site.register(CustomerGroup, TenantModelAdmin)


@admin.register(Customer)
class CustomerAdmin(TenantModelAdmin):
    list_display = (
        "id",
        "display_name",
        "company",
        "branch",
        "group",
        "customer_type",
        "phone",
        "email",
        "owed_amount",
        "wallet_balance",
        "status",
    )
    search_fields = (
        "first_name",
        "last_name",
        "phone",
        "email",
        "company_name",
        "code",
    )
    list_filter = ("company", "branch", "group", "customer_type", "status")


admin.site.register(CustomerAddress, TenantModelAdmin)
admin.site.register(CustomerWalletTransaction, TenantModelAdmin)
admin.site.register(CustomerCreditLedger, TenantModelAdmin)
