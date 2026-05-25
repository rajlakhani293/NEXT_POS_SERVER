from django.contrib import admin

from apps.common.admin import TenantModelAdmin
from apps.promotions.models import (
    AppliedCoupon,
    Coupon,
    CouponCategory,
    CouponProduct,
    CustomerCoupon,
)


admin.site.register(Coupon, TenantModelAdmin)
admin.site.register(CouponProduct, TenantModelAdmin)
admin.site.register(CouponCategory, TenantModelAdmin)
admin.site.register(CustomerCoupon, TenantModelAdmin)
admin.site.register(AppliedCoupon, TenantModelAdmin)
