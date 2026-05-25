from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.payments.models import PaymentMethod, RefundPayment, SalePayment


admin.site.register(PaymentMethod, TenantModelAdmin)
admin.site.register(SalePayment, TenantModelAdmin)
admin.site.register(RefundPayment, TenantModelAdmin)
