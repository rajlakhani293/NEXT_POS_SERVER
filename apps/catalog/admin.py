from django.contrib import admin
from decimal import Decimal

from apps.catalog.models import (
    Brand,
    Category,
    Product,
    ProductBundleItem,
    Tax,
    TaxGroup,
    Unit,
    UnitGroup,
)
from apps.common.admin import TenantModelAdmin


class ProductAdmin(TenantModelAdmin):
    @admin.display(description="After Tax")
    def tax_amount_preview(self, obj):
        if not obj.tax_group_id:
            return "-"

        tax_rate = sum(
            Decimal(str(tax.rate or 0))
            for tax in obj.tax_group.taxes.exclude(status=2)
        )
        selling_price = Decimal(str(obj.selling_price or 0))

        if obj.is_tax_inclusive:
            taxable_amount = selling_price / (Decimal("1") + (tax_rate / Decimal("100"))) if tax_rate else selling_price
            tax_amount = selling_price - taxable_amount
            return f"{selling_price:.2f} incl. {tax_amount:.2f} tax"

        tax_amount = selling_price * tax_rate / Decimal("100")
        amount_after_tax = selling_price + tax_amount
        return f"{selling_price:.2f} + {tax_amount:.2f}(tax) = {amount_after_tax:.2f}"

    def get_list_display(self, request):  # type: ignore
        fields = list(super().get_list_display(request))
        for field in ["selling_price", "tax_group", "is_tax_inclusive", "tax_amount_preview"]:
            if field not in fields:
                fields.append(field)
        return tuple(fields)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if "tax_amount_preview" not in fields:
            fields.append("tax_amount_preview")
        return tuple(fields)


admin.site.register(Category, TenantModelAdmin)
admin.site.register(Brand, TenantModelAdmin)
admin.site.register(UnitGroup, TenantModelAdmin)
admin.site.register(Unit, TenantModelAdmin)
admin.site.register(TaxGroup, TenantModelAdmin)
admin.site.register(Tax, TenantModelAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(ProductBundleItem, TenantModelAdmin)
