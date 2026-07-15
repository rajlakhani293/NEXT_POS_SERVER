from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.promotions.models import (
    OrdersCoupon,
    Coupon,
    CouponCategory,
    CouponCustomerGroup,
    CouponProduct,
)


admin.site.register(Coupon, TenantModelAdmin)
admin.site.register(CouponProduct, TenantModelAdmin)
admin.site.register(CouponCategory, TenantModelAdmin)
admin.site.register(CouponCustomerGroup, TenantModelAdmin)
admin.site.register(OrdersCoupon, TenantModelAdmin)
