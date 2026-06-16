# type: ignore
from django.contrib import admin

from apps.catalog.models import (
    Category,
    Product,
    ProductGallery,
    ProductHistory,
    ProductHistoryCombined,
    ProductMeta,
    ProductSubItem,
    ProductTax,
    ProductUnitQuantity,
    ScaleRange,
    Tax,
    TaxGroup,
    Unit,
    UnitGroup,
)
from apps.common.admin import TenantModelAdmin


class ProductGalleryInline(admin.TabularInline):
    model = ProductGallery
    extra = 0


class ProductUnitQuantityInline(admin.TabularInline):
    model = ProductUnitQuantity
    extra = 0


class ProductAdmin(TenantModelAdmin):
    inlines = [ProductGalleryInline, ProductUnitQuantityInline]


admin.site.register(ScaleRange, TenantModelAdmin)
admin.site.register(Category, TenantModelAdmin)
admin.site.register(UnitGroup, TenantModelAdmin)
admin.site.register(Unit, TenantModelAdmin)
admin.site.register(TaxGroup, TenantModelAdmin)
admin.site.register(Tax, TenantModelAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(ProductTax, TenantModelAdmin)
admin.site.register(ProductHistory, TenantModelAdmin)
admin.site.register(ProductHistoryCombined, TenantModelAdmin)
admin.site.register(ProductSubItem, TenantModelAdmin)
admin.site.register(ProductMeta, TenantModelAdmin)
