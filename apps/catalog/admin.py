# type: ignore
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from decimal import Decimal

from apps.catalog.models import (
    Brand,
    Category,
    Product,
    Tax,
    TaxGroup,
    Unit,
    UnitGroup,
)
from apps.common.admin import TenantModelAdmin


class ProductAdmin(TenantModelAdmin):
    class Media:
        js = ("catalog/admin/product_tax_preview.js",)

    def build_tax_preview_data(self, tax_group_id, selling_price, is_tax_inclusive):
        if not is_tax_inclusive:
            return {
                "preview": "Preview only for tax inclusive price",
                "amount_after_tax": None,
            }

        if not tax_group_id:
            return {"preview": "Select tax group and save", "amount_after_tax": None}

        tax_group = TaxGroup.objects.filter(id=tax_group_id).first()
        if not tax_group:
            return {"preview": "Select valid tax group", "amount_after_tax": None}

        tax_rate = sum(
            Decimal(str(tax.rate or 0))
            for tax in tax_group.taxes.exclude(status=2)
        )
        selling_price = Decimal(str(selling_price or 0))

        taxable_amount = selling_price / (Decimal("1") + (tax_rate / Decimal("100"))) if tax_rate else selling_price
        tax_amount = selling_price - taxable_amount
        amount_after_tax = selling_price + tax_amount
        return {
            "preview": f"{selling_price:.2f} + {tax_amount:.2f}(tax) = {amount_after_tax:.2f}",
            "amount_after_tax": f"{amount_after_tax:.2f}",
        }

    def build_tax_preview(self, tax_group_id, selling_price, is_tax_inclusive):
        return self.build_tax_preview_data(tax_group_id, selling_price, is_tax_inclusive)["preview"]

    @admin.display(description="After Tax")
    def tax_amount_preview(self, obj):
        return self.build_tax_preview(obj.tax_group_id, obj.selling_price, obj.is_tax_inclusive)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "tax-preview/",
                self.admin_site.admin_view(self.tax_preview_view),
                name="catalog_product_tax_preview",
            ),
        ]
        return custom_urls + urls

    def tax_preview_view(self, request):
        tax_group_id = request.GET.get("tax_group_id")
        selling_price = request.GET.get("selling_price") or 0
        is_tax_inclusive = request.GET.get("is_tax_inclusive") == "true"
        return JsonResponse(
            self.build_tax_preview_data(
                tax_group_id,
                selling_price,
                is_tax_inclusive,
            )
        )

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

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if "tax_amount_preview" in fields:
            fields.remove("tax_amount_preview")

        insert_after = "is_tax_inclusive"
        if insert_after in fields:
            fields.insert(fields.index(insert_after) + 1, "tax_amount_preview")
        else:
            fields.append("tax_amount_preview")

        return tuple(fields)


admin.site.register(Category, TenantModelAdmin)
admin.site.register(Brand, TenantModelAdmin)
admin.site.register(UnitGroup, TenantModelAdmin)
admin.site.register(Unit, TenantModelAdmin)
admin.site.register(TaxGroup, TenantModelAdmin)
admin.site.register(Tax, TenantModelAdmin)
admin.site.register(Product, ProductAdmin)
