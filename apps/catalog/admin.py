from django.contrib import admin

from apps.catalog.models import (
    Brand,
    Category,
    Product,
    ProductBarcode,
    ProductBundleItem,
    ProductImage,
    ProductVariant,
    Tax,
    TaxGroup,
    Unit,
    UnitGroup,
)
from apps.common.admin import TenantModelAdmin


admin.site.register(Category, TenantModelAdmin)
admin.site.register(Brand, TenantModelAdmin)
admin.site.register(UnitGroup, TenantModelAdmin)
admin.site.register(Unit, TenantModelAdmin)
admin.site.register(TaxGroup, TenantModelAdmin)
admin.site.register(Tax, TenantModelAdmin)
admin.site.register(Product, TenantModelAdmin)
admin.site.register(ProductVariant, TenantModelAdmin)
admin.site.register(ProductBarcode, TenantModelAdmin)
admin.site.register(ProductImage, TenantModelAdmin)
admin.site.register(ProductBundleItem, TenantModelAdmin)
