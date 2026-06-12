# type: ignore
from django.db import transaction
from apps.catalog.models import (
    Brand,
    Category,
    Product,
    ProductUnitQuantity,
    Tax,
    TaxGroup,
    Unit,
    UnitGroup,
)
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildSku, saveProductImage, validateTenantRelationId, validateUniqueFields
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
            validateUniqueFields(
                Unit,
                {"name": data.get("name")},
                scope=None,
                status_in=(0, 1),
                case_insensitive=["name"],
                extra_filters={"unit_group_id": unit_group["id"]},
                messages={"name": "Unit name already exists in this unit group."},
            )
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
            if "name" in data:
                validateUniqueFields(
                    Unit,
                    {"name": data.get("name")},
                    scope=None,
                    exclude_id=unit_id,
                    status_in=(0, 1),
                    case_insensitive=["name"],
                    extra_filters={"unit_group_id": data.get("unit_group_id") or unit["unit_group_id"]},
                    messages={"name": "Unit name already exists in this unit group."},
                )
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
            validateUniqueFields(
                Product,
                {"barcode": data.get("barcode")},
                request=request,
                scope="branch",
                status_in=(0, 1),
                messages={"barcode": "Barcode already exists on another product."},
            )
            data["current_stock"] = data.get("opening_stock", 0)
            image_url = saveProductImage(image, request)
            if image_url:
                data["image"] = image_url

            category_id = None
            brand_id = None
            tax_group_id = None
            if data.get("category_id"):
                category_id = validateTenantRelationId(
                    Category, data["category_id"], request=request, label="Category"
                )
            if data.get("brand_id"):
                brand_id = validateTenantRelationId(
                    Brand, data["brand_id"], request=request, label="Brand"
                )
            if data.get("tax_group_id"):
                tax_group_id = validateTenantRelationId(
                    TaxGroup, data["tax_group_id"], request=request, label="Tax group"
                )
            unit_id = validateTenantRelationId(
                Unit,
                data.get("unit_id"),
                request=request,
                label="Unit",
                required=True,
            )

            product = commonQuery.createRecord(
                Product,
                { 
                    **data,
                    "category_id": category_id,
                    "brand_id": brand_id,
                    "tax_group_id": tax_group_id,
                    "unit_id": unit_id,
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
                data["category_id"] = validateTenantRelationId(
                    Category, data["category_id"], request=request, label="Category"
                )
            if data.get("brand_id"):
                data["brand_id"] = validateTenantRelationId(
                    Brand, data["brand_id"], request=request, label="Brand"
                )
            if data.get("tax_group_id"):
                data["tax_group_id"] = validateTenantRelationId(
                    TaxGroup, data["tax_group_id"], request=request, label="Tax group"
                )
            if data.get("unit_id"):
                data["unit_id"] = validateTenantRelationId(
                    Unit, data["unit_id"], request=request, label="Unit"
                )
            if "sku" in data:
                data["sku"] = buildSku(
                    Product,
                    data.get("name") or product["name"],
                    data.get("sku") or product["sku"],
                    request,
                    exclude_id=product["id"],
                )
            if "barcode" in data:
                validateUniqueFields(
                    Product,
                    {"barcode": data.get("barcode")},
                    request=request,
                    scope="branch",
                    exclude_id=product["id"],
                    status_in=(0, 1),
                    messages={"barcode": "Barcode already exists on another product."},
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
            {"attributes": ["id", "name", "sku", "barcode", "selling_price", "purchase_price", "current_stock", "unit_id"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def searchUsingBarcode(reference, request):
        if not reference:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Barcode is required.")

        product = commonQuery.findOneRecord(
            Product,
            {"barcode": reference},
            request=request,
            tenant_config=True,
        )
        if product:
            product = ProductService.attachDisplayData(dict(product), request)
            product["matched_unit_quantity"] = None
            return successResponse("Product retrieved successfully.", data=product)

        unit_quantity = commonQuery.findOneRecord(
            ProductUnitQuantity,
            {"barcode": reference},
            options={
                "include": [
                    {"path": "product", "fields": ["id", "name", "sku", "barcode", "selling_price", "purchase_price", "current_stock", "unit_id", "status"]},
                    {"path": "unit", "fields": ["id", "name", "short_name"]},
                    {"path": "convert_unit", "fields": ["id", "name", "short_name"]},
                ]
            },
            request=request,
            tenant_config=True,
        )
        if unit_quantity is None:
            unit_quantity = commonQuery.findOneRecord(
                ProductUnitQuantity,
                {"scale_plu": reference},
                options={
                    "include": [
                        {"path": "product", "fields": ["id", "name", "sku", "barcode", "selling_price", "purchase_price", "current_stock", "unit_id", "status"]},
                        {"path": "unit", "fields": ["id", "name", "short_name"]},
                        {"path": "convert_unit", "fields": ["id", "name", "short_name"]},
                    ]
                },
                request=request,
                tenant_config=True,
            )
        if unit_quantity is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")

        product_data = unit_quantity.get("product") or {}
        product_data = ProductService.attachDisplayData(dict(product_data), request)
        product_data["matched_unit_quantity"] = {
            "id": unit_quantity.get("id"),
            "unit_id": unit_quantity.get("unit_id"),
            "unit": unit_quantity.get("unit"),
            "convert_unit_id": unit_quantity.get("convert_unit_id"),
            "convert_unit": unit_quantity.get("convert_unit"),
            "barcode": unit_quantity.get("barcode"),
            "quantity": unit_quantity.get("quantity"),
            "sale_price": unit_quantity.get("sale_price"),
            "purchase_price": unit_quantity.get("purchase_price"),
            "is_default": unit_quantity.get("is_default"),
            "scale_plu": unit_quantity.get("scale_plu"),
        }
        return successResponse("Product retrieved successfully.", data=product_data)

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


class ProductUnitQuantityService:
    @staticmethod
    def attachDisplayData(data):
        unit = data.get("unit") or {}
        convert_unit = data.get("convert_unit") or {}
        data["unit_name"] = unit.get("name") if unit else None
        data["unit_short_name"] = unit.get("short_name") if unit else None
        data["convert_unit_name"] = convert_unit.get("name") if convert_unit else None
        data["convert_unit_short_name"] = convert_unit.get("short_name") if convert_unit else None
        return data

    @staticmethod
    def ensureProduct(product_id, request):
        product = commonQuery.findOneRecord(
            Product,
            product_id,
            request=request,
            tenant_config=True,
        )
        if product is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        return product

    @staticmethod
    def ensureUnit(unit_id, request, label="Unit"):
        unit = commonQuery.findOneRecord(
            Unit,
            unit_id,
            request=request,
            tenant_config=True,
        )
        if unit is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, f"{label} not found.")
        return unit

    @staticmethod
    def ensureBarcodeAvailable(barcode, request, unit_quantity_id=None):
        if not barcode:
            return
        validateUniqueFields(
            Product,
            {"barcode": barcode},
            request=request,
            scope="branch",
            status_in=(0, 1),
            messages={"barcode": "Barcode already exists on another product."},
        )
        validateUniqueFields(
            ProductUnitQuantity,
            {"barcode": barcode},
            request=request,
            scope="branch",
            exclude_id=unit_quantity_id,
            status_in=(0, 1),
            messages={"barcode": "Barcode already exists on another selling unit."},
        )

    @staticmethod
    def getAll(product_id, request):
        ProductUnitQuantityService.ensureProduct(product_id, request)
        rows = commonQuery.findAllRecords(
            ProductUnitQuantity,
            {"product_id": product_id},
            {
                "include": [
                    {"path": "unit", "fields": ["id", "name", "short_name"]},
                    {"path": "convert_unit", "fields": ["id", "name", "short_name"]},
                ],
                "order": ["-is_default", "id"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse(
            "Product unit quantities retrieved successfully.",
            data=[ProductUnitQuantityService.attachDisplayData(dict(row)) for row in rows],
        )

    @staticmethod
    def create(product_id, data, request):
        with transaction.atomic():
            product = ProductUnitQuantityService.ensureProduct(product_id, request)
            unit = ProductUnitQuantityService.ensureUnit(data["unit_id"], request)
            convert_unit = None
            if data.get("convert_unit_id"):
                convert_unit = ProductUnitQuantityService.ensureUnit(data["convert_unit_id"], request, "Convert unit")
            if data.get("barcode") == "":
                data["barcode"] = None
            ProductUnitQuantityService.ensureBarcodeAvailable(data.get("barcode"), request)

            validateUniqueFields(
                ProductUnitQuantity,
                {"unit_id": unit["id"]},
                request=request,
                scope=None,
                status_in=(0, 1),
                extra_filters={"product_id": product["id"]},
                messages={"unit_id": "This unit already exists for this product."},
            )

            if data.get("is_default"):
                ProductUnitQuantity.objects.filter(product_id=product["id"], status__in=[0, 1]).update(is_default=False)

            unit_quantity = commonQuery.createRecord(
                ProductUnitQuantity,
                {
                    **data,
                    "product_id": product["id"],
                    "unit_id": unit["id"],
                    "convert_unit_id": convert_unit["id"] if convert_unit else None,
                },
                request=request,
                tenant_config=True,
            )
            return successResponse("Product unit quantity created successfully.", data=unit_quantity)

    @staticmethod
    def update(product_id, unit_quantity_id, data, request):
        with transaction.atomic():
            product = ProductUnitQuantityService.ensureProduct(product_id, request)
            unit_quantity = commonQuery.findOneRecord(
                ProductUnitQuantity,
                {"id": unit_quantity_id, "product_id": product["id"]},
                request=request,
                tenant_config=True,
            )
            if unit_quantity is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product unit quantity not found.")

            if data.get("unit_id"):
                unit = ProductUnitQuantityService.ensureUnit(data["unit_id"], request)
                validateUniqueFields(
                    ProductUnitQuantity,
                    {"unit_id": unit["id"]},
                    request=request,
                    scope=None,
                    exclude_id=unit_quantity_id,
                    status_in=(0, 1),
                    extra_filters={"product_id": product["id"]},
                    messages={"unit_id": "This unit already exists for this product."},
                )
                data["unit_id"] = unit["id"]

            if data.get("convert_unit_id"):
                convert_unit = ProductUnitQuantityService.ensureUnit(data["convert_unit_id"], request, "Convert unit")
                data["convert_unit_id"] = convert_unit["id"]
            elif "convert_unit_id" in data:
                data["convert_unit_id"] = None
            if data.get("barcode") == "":
                data["barcode"] = None
            ProductUnitQuantityService.ensureBarcodeAvailable(data.get("barcode"), request, unit_quantity_id)

            if data.get("is_default"):
                ProductUnitQuantity.objects.filter(product_id=product["id"], status__in=[0, 1]).exclude(id=unit_quantity_id).update(is_default=False)

            updated = commonQuery.updateRecordById(
                ProductUnitQuantity,
                {"id": unit_quantity_id, "product_id": product["id"]},
                data,
                request=request,
                tenant_config=True,
            )
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product unit quantity not found.")
            return successResponse("Product unit quantity updated successfully.", data=updated)

    @staticmethod
    def delete(product_id, unit_quantity_id, request):
        ProductUnitQuantityService.ensureProduct(product_id, request)
        count = commonQuery.softDeleteById(
            ProductUnitQuantity,
            {"id": unit_quantity_id, "product_id": product_id},
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product unit quantity not found.")
        return successResponse("Product unit quantity deleted successfully.")
