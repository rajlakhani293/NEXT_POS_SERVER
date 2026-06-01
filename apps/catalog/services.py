# type: ignore
from django.db import transaction
from apps.catalog.models import (
    Brand,
    Category,
    Product,
    Tax,
    TaxGroup,
    Unit,
    UnitGroup,
)
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildSku, saveProductImage
from apps.common.responses import successResponse


class CategoryService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            parent = None
            if data.get("parent_id"):
                parent = commonQuery.findOneRecord(
                    Category,
                    data["parent_id"],
                    request=request,
                    tenant_config=True,
                )
                if parent is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Parent category not found.")

            category = commonQuery.createRecord(
                Category,
                {
                    **data,
                    "parent_id": parent["id"] if parent else None,
                },
                request=request,
                tenant_config=True,
            )
            category_data = dict(category)
            category_data["parent_name"] = parent["name"] if parent else None
            return successResponse(
                "Category created successfully.",
                data=category_data,
            )

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True]]
        options = {
            "attributes": ["id", "name", "description", "parent_id", "status"],
        }
        result = commonQuery.fetchPaginatedData(Category, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Categories retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Category,
            {},
            {"attributes": ["id", "name"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getById(category_id, request):
        category = commonQuery.findOneRecord(
            Category,
            category_id,
            request=request,
            tenant_config=True,
        )
        if category is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
        category_data = dict(category)
        category_data["parent_name"] = None
        if category.get("parent_id"):
            parent = commonQuery.findOneRecord(
                Category,
                category["parent_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            category_data["parent_name"] = parent["name"] if parent else None
        return successResponse(
            "Category retrieved successfully.",
            data=category_data,
        )

    @staticmethod
    def update(data, request, category_id):
        with transaction.atomic():
            category = commonQuery.findOneRecord(
                Category,
                category_id,
                request=request,
                tenant_config=True,
            )
            if category is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
            if data.get("parent_id"):
                parent = commonQuery.findOneRecord(
                    Category,
                    data["parent_id"],
                    request=request,
                    tenant_config=True,
                )
                if parent is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Parent category not found.")
                data["parent_id"] = parent["id"]
            category_data = commonQuery.updateRecordById(
                Category,
                category_id,
                data,
                request=request,
                tenant_config=True,
            )
            if category_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
            category_data["parent_name"] = None
            if category_data.get("parent_id"):
                parent = commonQuery.findOneRecord(
                    Category,
                    category_data["parent_id"],
                    options={"attributes": ["name"]},
                    request=request,
                    tenant_config=True,
                )
                category_data["parent_name"] = parent["name"] if parent else None
            return successResponse(
                "Category updated successfully.",
                data=category_data,
            )

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(
            Category,
            data.get("ids"),
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
        return successResponse("Categories deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            Category,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
        return successResponse("Category status updated successfully.", data={"updated_count": count, "status": status})

class BrandService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            brand = commonQuery.createRecord(
                Brand,
                data,
                request=request,
                tenant_config=True,
            )
            return successResponse("Brand created successfully.", data=brand)

    @staticmethod
    def update(data, request, brand_id):
        with transaction.atomic():
            brand = commonQuery.findOneRecord(
                Brand,
                brand_id,
                request=request,
                tenant_config=True,
            )
            if brand is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Brand not found.")
            brand_data = commonQuery.updateRecordById(Brand, brand_id, data, request=request, tenant_config=True)
            if brand_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Brand not found.")
            return successResponse("Brand updated successfully.", data=brand_data)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True]]
        options = {"attributes": ["id", "name", "description", "status"]}
        result = commonQuery.fetchPaginatedData(Brand, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Brands retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Brand,
            {},
            {"attributes": ["id", "name"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Brand, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Brand not found.")
        return successResponse("Brands deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            Brand,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Brand not found.")
        return successResponse("Brand status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(brand_id, request):
        brand = commonQuery.findOneRecord(
            Brand,
            brand_id,
            request=request,
            tenant_config=True,
        )
        if brand is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Brand not found.")
        return successResponse("Brand retrieved successfully.", data=brand)


class UnitGroupService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            unit_group = commonQuery.createRecord(
                UnitGroup,
                data,
                request=request,
                tenant_config=True,
            )
            unit_group_data = dict(unit_group)
            unit_group_data["units_count"] = 0
            return successResponse(
                "Unit group created successfully.",
                data=unit_group_data,
            )

    @staticmethod
    def update(data, request, unit_group_id):
        with transaction.atomic():
            unit_group = commonQuery.findOneRecord(
                UnitGroup,
                unit_group_id,
                request=request,
                tenant_config=True,
            )
            if unit_group is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
            unit_group_data = commonQuery.updateRecordById(
                UnitGroup,
                unit_group_id,
                data,
                request=request,
                tenant_config=True,
            )
            if unit_group_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
            unit_group_data["units_count"] = commonQuery.countRecords(
                Unit,
                {"unit_group_id": unit_group_id},
                request=request,
                tenant_config=True,
            )
            return successResponse(
                "Unit group updated successfully.",
                data=unit_group_data,
            )

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True]]
        options = {"attributes": ["id", "name", "description", "status"]}
        result = commonQuery.fetchPaginatedData(UnitGroup, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Unit groups retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            UnitGroup,
            {},
            {"attributes": ["id", "name"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(UnitGroup, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
        return successResponse("Unit groups deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            UnitGroup,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
        return successResponse("Unit group status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(unit_group_id, request):
        unit_group = commonQuery.findOneRecord(
            UnitGroup,
            unit_group_id,
            request=request,
            tenant_config=True,
        )
        if unit_group is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
        unit_group_data = dict(unit_group)
        unit_group_data["units_count"] = commonQuery.countRecords(
            Unit,
            {"unit_group_id": unit_group_id},
            request=request,
            tenant_config=True,
        )
        return successResponse(
            "Unit group retrieved successfully.",
            data=unit_group_data,
        )


class UnitService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            unit_group = commonQuery.findOneRecord(
                UnitGroup,
                data["unit_group_id"],
                request=request,
                tenant_config=True,
            )
            if unit_group is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
            if data.get("is_base_unit"):
                Unit.objects.filter(unit_group_id=unit_group["id"]).update(is_base_unit=False)
            unit = commonQuery.createRecord(
                Unit,
                {**data, "unit_group_id": unit_group["id"]},
                request=request,
                tenant_config=True,
            )
            unit_data = dict(unit)
            unit_data["unit_group_name"] = unit_group["name"] if unit_group else None
            return successResponse("Unit created successfully.", data=unit_data)

    @staticmethod
    def update(data, request, unit_id):
        with transaction.atomic():
            unit = commonQuery.findOneRecord(
                Unit,
                unit_id,
                request=request,
                tenant_config=True,
            )
            if unit is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
            if data.get("unit_group_id"):
                unit_group = commonQuery.findOneRecord(
                    UnitGroup,
                    data["unit_group_id"],
                    request=request,
                    tenant_config=True,
                )
                if unit_group is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
                data["unit_group_id"] = unit_group["id"]
            if data.get("is_base_unit"):
                Unit.objects.filter(unit_group_id=data.get("unit_group_id") or unit["unit_group_id"]).exclude(id=unit_id).update(is_base_unit=False)
            unit_data = commonQuery.updateRecordById(Unit, unit_id, data, request=request, tenant_config=True)
            if unit_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
            unit_data["unit_group_name"] = None
            if unit_data.get("unit_group_id"):
                unit_group = commonQuery.findOneRecord(
                    UnitGroup,
                    unit_data["unit_group_id"],
                    options={"attributes": ["name"]},
                    request=request,
                    tenant_config=True,
                )
                unit_data["unit_group_name"] = unit_group["name"] if unit_group else None
            return successResponse("Unit updated successfully.", data=unit_data)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["short_name", True, True]]
        options = {
            "attributes": ["id", "name", "short_name", "factor", "is_base_unit", "unit_group_id", "status"],
        }
        result = commonQuery.fetchPaginatedData(Unit, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Units retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Unit,
            {},
            {"attributes": ["id", "name", "short_name", "unit_group_id"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Unit, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
        return successResponse("Units deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            Unit,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
        return successResponse("Unit status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(unit_id, request):
        unit = commonQuery.findOneRecord(
            Unit,
            unit_id,
            request=request,
            tenant_config=True,
        )
        if unit is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
        unit_data = dict(unit)
        unit_data["unit_group_name"] = None
        if unit.get("unit_group_id"):
            unit_group = commonQuery.findOneRecord(
                UnitGroup,
                unit["unit_group_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            unit_data["unit_group_name"] = unit_group["name"] if unit_group else None
        return successResponse("Unit retrieved successfully.", data=unit_data)


class TaxGroupService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            tax_group = commonQuery.createRecord(
                TaxGroup,
                data,
                request=request,
                tenant_config=True,
            )
            tax_group_data = dict(tax_group)
            tax_group_data["taxes_count"] = 0
            return successResponse(
                "Tax group created successfully.",
                data=tax_group_data,
            )

    @staticmethod
    def update(data, request, tax_group_id):
        with transaction.atomic():
            tax_group = commonQuery.findOneRecord(
                TaxGroup,
                tax_group_id,
                request=request,
                tenant_config=True,
            )
            if tax_group is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
            tax_group_data = commonQuery.updateRecordById(
                TaxGroup,
                tax_group_id,
                data,
                request=request,
                tenant_config=True,
            )
            if tax_group_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
            tax_group_data["taxes_count"] = commonQuery.countRecords(
                Tax,
                {"tax_group_id": tax_group_id},
                request=request,
                tenant_config=True,
            )
            return successResponse(
                "Tax group updated successfully.",
                data=tax_group_data,
            )

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True]]
        options = {"attributes": ["id", "name", "description", "status"]}
        result = commonQuery.fetchPaginatedData(TaxGroup, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Tax groups retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            TaxGroup,
            {},
            {
                "attributes": ["id", "name"],
                "include": [{"path": "taxes", "fields": ["id", "name", "rate", "status"]}],
                "order": ["name"],
            },
            request=request,
            tenant_config=True,
        )
        for group in data:
            taxes = group.pop("taxes", None) or []
            active_taxes = []
            total_rate = 0.0
            for tax in taxes:
                if tax.get("status") != 2:
                    rate_val = float(tax.get("rate") or 0)
                    total_rate += rate_val
                    active_taxes.append({
                        "id": tax.get("id"),
                        "name": tax.get("name"),
                        "rate": rate_val,
                    })
            group["rate"] = total_rate
            group["taxes"] = active_taxes
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(TaxGroup, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
        return successResponse("Tax groups deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            TaxGroup,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
        return successResponse("Tax group status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(tax_group_id, request):
        tax_group = commonQuery.findOneRecord(
            TaxGroup,
            tax_group_id,
            request=request,
            tenant_config=True,
        )
        if tax_group is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
        tax_group_data = dict(tax_group)
        tax_group_data["taxes_count"] = commonQuery.countRecords(
            Tax,
            {"tax_group_id": tax_group_id},
            request=request,
            tenant_config=True,
        )
        return successResponse(
            "Tax group retrieved successfully.",
            data=tax_group_data,
        )


class TaxService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            tax_group = commonQuery.findOneRecord(
                TaxGroup,
                data["tax_group_id"],
                request=request,
                tenant_config=True,
            )
            if tax_group is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
            tax = commonQuery.createRecord(
                Tax,
                {**data, "tax_group_id": tax_group["id"]},
                request=request,
                tenant_config=True,
            )
            return successResponse("Tax created successfully.", None)

    @staticmethod
    def update(data, request, tax_id):
        with transaction.atomic():
            tax = commonQuery.findOneRecord(
                Tax,
                tax_id,
                request=request,
                tenant_config=True,
            )
            if tax is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Tax not found.")
            if data.get("tax_group_id"):
                tax_group = commonQuery.findOneRecord(
                    TaxGroup,
                    data["tax_group_id"],
                    request=request,
                    tenant_config=True,
                )
                if tax_group is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
                data["tax_group_id"] = tax_group["id"]
            tax_data = commonQuery.updateRecordById(Tax, tax_id, data, request=request, tenant_config=True)
            if tax_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Tax not found.")
            return successResponse("Tax updated successfully.", None)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["rate", False, True]]
        options = {
            "attributes": ["id", "name", "rate", "tax_group_id", "tax_group__name", "status"]
        }
        result = commonQuery.fetchPaginatedData(Tax, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Taxes retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Tax,
            {},
            {"attributes": ["id", "name", "rate", "tax_group_id", "tax_group__name"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Tax, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax not found.")
        return successResponse("Taxes deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            Tax,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax not found.")
        return successResponse("Tax status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(tax_id, request):
        tax = commonQuery.findOneRecord(Tax, tax_id, {},request, True)
        if tax is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax not found.")
        return successResponse("Tax retrieved successfully.", data=tax)


class ProductService:
    @staticmethod
    def attachDisplayData(product_data, request):
        product_data["category_name"] = None
        product_data["brand_name"] = None
        product_data["tax_group_name"] = None
        product_data["unit_name"] = None

        if product_data.get("category_id"):
            category = commonQuery.findOneRecord(
                Category,
                product_data["category_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            product_data["category_name"] = category["name"] if category else None
        if product_data.get("brand_id"):
            brand = commonQuery.findOneRecord(
                Brand,
                product_data["brand_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            product_data["brand_name"] = brand["name"] if brand else None
        if product_data.get("tax_group_id"):
            tax_group = commonQuery.findOneRecord(
                TaxGroup,
                product_data["tax_group_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            product_data["tax_group_name"] = tax_group["name"] if tax_group else None
        if product_data.get("unit_id"):
            unit = commonQuery.findOneRecord(
                Unit,
                product_data["unit_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            product_data["unit_name"] = unit["name"] if unit else None

        return product_data

    @staticmethod
    def create(data, request, image=None):
        with transaction.atomic():
            if data.get("sku") == "":
                data["sku"] = None
            if data.get("barcode") == "":
                data["barcode"] = None
            data["sku"] = buildSku(Product, data.get("name"), data.get("sku"), request)
            data["current_stock"] = data.get("opening_stock", 0)
            image_url = saveProductImage(image, request)
            if image_url:
                data["image"] = image_url

            category = None
            brand = None
            tax_group = None
            unit = None
            if data.get("category_id"):
                category = commonQuery.findOneRecord(
                    Category, data["category_id"], request=request, tenant_config=True
                )
                if category is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
            if data.get("brand_id"):
                brand = commonQuery.findOneRecord(
                    Brand, data["brand_id"], request=request, tenant_config=True
                )
                if brand is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Brand not found.")
            if data.get("tax_group_id"):
                tax_group = commonQuery.findOneRecord(
                    TaxGroup, data["tax_group_id"], request=request, tenant_config=True
                )
                if tax_group is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
            unit = commonQuery.findOneRecord(
                Unit, data["unit_id"], request=request, tenant_config=True
            )
            if unit is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")

            product = commonQuery.createRecord(
                Product,
                { 
                    **data,
                    "category_id": category["id"] if category else None,
                    "brand_id": brand["id"] if brand else None,
                    "tax_group_id": tax_group["id"] if tax_group else None,
                    "unit_id": unit["id"] if unit else None,
                },
                request=request,
                tenant_config=True,
            )
            product_data = dict(product)
            product_data = ProductService.attachDisplayData(product_data, request)
            return successResponse("Product created successfully.", data=product_data)

    @staticmethod
    def update(data, request, product_id, image=None):
        with transaction.atomic():
            if data.get("sku") == "":
                data["sku"] = None
            if data.get("barcode") == "":
                data["barcode"] = None
            image_url = saveProductImage(image, request)
            if image_url:
                data["image"] = image_url

            product = commonQuery.findOneRecord(
                Product,
                product_id,
                request=request,
                tenant_config=True,
            )
            if product is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
            if data.get("category_id"):
                category = commonQuery.findOneRecord(
                    Category, data["category_id"], request=request, tenant_config=True
                )
                if category is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
                data["category_id"] = category["id"]
            if data.get("brand_id"):
                brand = commonQuery.findOneRecord(
                    Brand, data["brand_id"], request=request, tenant_config=True
                )
                if brand is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Brand not found.")
                data["brand_id"] = brand["id"]
            if data.get("tax_group_id"):
                tax_group = commonQuery.findOneRecord(
                    TaxGroup, data["tax_group_id"], request=request, tenant_config=True
                )
                if tax_group is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
                data["tax_group_id"] = tax_group["id"]
            if data.get("unit_id"):
                unit = commonQuery.findOneRecord(
                    Unit, data["unit_id"], request=request, tenant_config=True
                )
                if unit is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
                data["unit_id"] = unit["id"]
            if "sku" in data:
                data["sku"] = buildSku(
                    Product,
                    data.get("name") or product["name"],
                    data.get("sku") or product["sku"],
                    request,
                    exclude_id=product["id"],
                )
            product_data = commonQuery.updateRecordById(Product, product_id, data, request=request, tenant_config=True)
            if product_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
            product_data = ProductService.attachDisplayData(product_data, request)
            return successResponse("Product updated successfully.", data=product_data)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["sku", True, True], ["product_type", False, True]]
        options = {
            "attributes": [
                "id",
                "name",
                "sku",
                "barcode",
                "image",
                "weight",
                "product_type",
                "purchase_price",
                "selling_price",
                "mrp",
                "wholesale_price",
                "is_tax_inclusive",
                "current_stock",
                "opening_stock",
                "min_stock",
                "max_stock",
                "track_stock",
                "allow_decimal_qty",
                "expiry_tracking_enabled",
                "category_id",
                "brand_id",
                "unit_id",
                "tax_group_id",
                "status",
            ],
        }
        result = commonQuery.fetchPaginatedData(Product, data, fieldConfig, options, request=request, tenant_config=True)
        result["items"] = [ProductService.attachDisplayData(item, request) for item in result["items"]]
        return successResponse("Products retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Product,
            {},
            {"attributes": ["id", "name", "sku", "barcode", "selling_price", "current_stock"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Product, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        return successResponse("Products deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            Product,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        return successResponse("Product status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(product_id, request):
        product = commonQuery.findOneRecord(
            Product,
            product_id,
            request=request,
            tenant_config=True,
        )
        if product is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        product_data = dict(product)
        product_data = ProductService.attachDisplayData(product_data, request)
        return successResponse("Product retrieved successfully.", data=product_data)
