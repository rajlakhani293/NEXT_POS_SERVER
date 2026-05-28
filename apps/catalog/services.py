# type: ignore
from django.db import transaction
from django.utils.text import slugify
from apps.catalog.models import (
    Brand,
    Category,
    Product,
    ProductBranch,
    ProductVariant,
    ProductVariantBranch,
    Tax,
    TaxGroup,
    Unit,
    UnitGroup,
)
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import serializeModelInstance
from apps.common.responses import successResponse


def buildUniqueValue(model, request, field_name, raw_value, exclude_id=None):
    value = raw_value
    counter = 1

    while True:
        record = commonQuery.findOneRecord(
            model,
            {field_name: value},
            request=request,
            tenant_config=True,
        )
        if not record or (exclude_id is not None and record.get("id") == exclude_id):
            return value
        counter += 1
        value = f"{raw_value}-{counter}"


def buildCode(model, name, code, request, exclude_id=None):
    raw_code = (code or "").strip()
    raw_name = (name or "").strip()
    base = slugify(raw_code or raw_name or "item") or "item"
    return buildUniqueValue(model, request, "code", base, exclude_id=exclude_id)


def buildSlug(model, name, slug, request, exclude_id=None):
    raw_slug = (slug or "").strip()
    raw_name = (name or "").strip()
    base = slugify(raw_slug or raw_name or "product") or "product"
    return buildUniqueValue(model, request, "slug", base, exclude_id=exclude_id)


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
                    "code": buildCode(Category, data.get("name"), data.get("code"), request),
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
        fieldConfig = [["name", True, True], ["code", True, True]]
        options = {
            "attributes": ["id", "name", "code", "description", "parent_id", "status"],
        }
        result = commonQuery.fetchPaginatedData(Category, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Categories retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Category,
            {},
            {"attributes": ["id", "name", "code"], "order": ["name"]},
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
            if data.get("code") is not None or data.get("name") is not None:
                data["code"] = buildCode(
                    Category,
                    data.get("name") or category["name"],
                    data.get("code") or category["code"],
                    request,
                    exclude_id=category["id"],
                )
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
                {
                    **data,
                    "code": buildCode(Brand, data.get("name"), data.get("code"), request),
                },
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
            if data.get("code") is not None or data.get("name") is not None:
                data["code"] = buildCode(
                    Brand,
                    data.get("name") or brand["name"],
                    data.get("code") or brand["code"],
                    request,
                    exclude_id=brand["id"],
                )
            brand_data = commonQuery.updateRecordById(Brand, brand_id, data, request=request, tenant_config=True)
            if brand_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Brand not found.")
            return successResponse("Brand updated successfully.", data=brand_data)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["code", True, True]]
        options = {"attributes": ["id", "name", "code", "description", "status"]}
        result = commonQuery.fetchPaginatedData(Brand, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Brands retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Brand,
            {},
            {"attributes": ["id", "name", "code"], "order": ["name"]},
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
                {
                    **data,
                    "code": buildCode(UnitGroup, data.get("name"), data.get("code"), request),
                },
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
            if data.get("code") is not None or data.get("name") is not None:
                data["code"] = buildCode(
                    UnitGroup,
                    data.get("name") or unit_group["name"],
                    data.get("code") or unit_group["code"],
                    request,
                    exclude_id=unit_group["id"],
                )
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
        fieldConfig = [["name", True, True], ["code", True, True]]
        options = {"attributes": ["id", "name", "code", "description", "status"]}
        result = commonQuery.fetchPaginatedData(UnitGroup, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Unit groups retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            UnitGroup,
            {},
            {"attributes": ["id", "name", "code"], "order": ["name"]},
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
                {
                    **data,
                    "code": buildCode(TaxGroup, data.get("name"), data.get("code"), request),
                },
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
            if data.get("code") is not None or data.get("name") is not None:
                data["code"] = buildCode(
                    TaxGroup,
                    data.get("name") or tax_group["name"],
                    data.get("code") or tax_group["code"],
                    request,
                    exclude_id=tax_group["id"],
                )
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
        fieldConfig = [["name", True, True], ["code", True, True]]
        options = {"attributes": ["id", "name", "code", "description", "status"]}
        result = commonQuery.fetchPaginatedData(TaxGroup, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Tax groups retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            TaxGroup,
            {},
            {"attributes": ["id", "name", "code"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
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
            tax_data = dict(tax)
            tax_data["tax_group_name"] = tax_group["name"] if tax_group else None
            return successResponse("Tax created successfully.", data=tax_data)

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
            tax_data["tax_group_name"] = None
            if tax_data.get("tax_group_id"):
                tax_group = commonQuery.findOneRecord(
                    TaxGroup,
                    tax_data["tax_group_id"],
                    options={"attributes": ["name"]},
                    request=request,
                    tenant_config=True,
                )
                tax_data["tax_group_name"] = tax_group["name"] if tax_group else None
            return successResponse("Tax updated successfully.", data=tax_data)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["rate", False, True]]
        options = {
            "attributes": ["id", "name", "rate", "is_inclusive", "tax_group_id", "status"],
        }
        result = commonQuery.fetchPaginatedData(Tax, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Taxes retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Tax,
            {},
            {"attributes": ["id", "name", "rate", "tax_group_id"], "order": ["name"]},
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
        tax = commonQuery.findOneRecord(
            Tax,
            tax_id,
            request=request,
            tenant_config=True,
        )
        if tax is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax not found.")
        tax_data = dict(tax)
        tax_data["tax_group_name"] = None
        if tax.get("tax_group_id"):
            tax_group = commonQuery.findOneRecord(
                TaxGroup,
                tax["tax_group_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            tax_data["tax_group_name"] = tax_group["name"] if tax_group else None
        return successResponse("Tax retrieved successfully.", data=tax_data)


class ProductService:
    BRANCH_FIELDS = [
        "purchase_price",
        "selling_price",
        "mrp",
        "wholesale_price",
        "current_stock",
        "opening_stock",
        "min_stock",
        "max_stock",
        "reorder_level",
        "stock_alert_enabled",
    ]

    @staticmethod
    def branchDataFromPayload(data):
        return {field: data[field] for field in ProductService.BRANCH_FIELDS if field in data}

    @staticmethod
    def masterDataFromPayload(data):
        return {key: value for key, value in data.items() if key not in ProductService.BRANCH_FIELDS}

    @staticmethod
    def attachBranchData(product_data, request):
        product_branch = commonQuery.findOneRecord(
            ProductBranch,
            {"product_id": product_data["id"]},
            request=request,
            tenant_config=True,
        )

        for field in ProductService.BRANCH_FIELDS:
            product_data[field] = product_branch.get(field) if product_branch else 0
        if not product_branch:
            product_data["stock_alert_enabled"] = True
        return product_data

    @staticmethod
    def create(data, request):
        with transaction.atomic():
            branch_data = ProductService.branchDataFromPayload(data)
            data = ProductService.masterDataFromPayload(data)
            if data.get("barcode") == "":
                data["barcode"] = None

            category = None
            brand = None
            tax_group = None
            unit = None
            unit_group = None
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
            if data.get("unit_id"):
                unit = commonQuery.findOneRecord(
                    Unit, data["unit_id"], request=request, tenant_config=True
                )
                if unit is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
            if data.get("unit_group_id"):
                unit_group = commonQuery.findOneRecord(
                    UnitGroup, data["unit_group_id"], request=request, tenant_config=True
                )
                if unit_group is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
            if unit and not unit_group and unit.get("unit_group_id"):
                unit_group = commonQuery.findOneRecord(
                    UnitGroup,
                    unit["unit_group_id"],
                    request=request,
                    tenant_config=True,
                )

            product = commonQuery.createRecord(
                Product,
                {
                    **data,
                    "slug": buildSlug(Product, data.get("name"), data.get("slug"), request),
                    "category_id": category["id"] if category else None,
                    "brand_id": brand["id"] if brand else None,
                    "tax_group_id": tax_group["id"] if tax_group else None,
                    "unit_id": unit["id"] if unit else None,
                    "unit_group_id": unit_group["id"] if unit_group else None,
                },
                request=request,
                tenant_config=True,
            )
            commonQuery.createRecord(
                ProductBranch,
                {
                    **branch_data,
                    "product_id": product["id"],
                },
                request=request,
                tenant_config=True,
            )
            product_data = dict(product)
            product_data = ProductService.attachBranchData(product_data, request)
            product_data["category_name"] = category["name"] if category else None
            product_data["brand_name"] = brand["name"] if brand else None
            product_data["tax_group_name"] = tax_group["name"] if tax_group else None
            product_data["unit_name"] = unit["name"] if unit else None
            product_data["unit_group_name"] = unit_group["name"] if unit_group else None
            product_data["variants_count"] = 0
            return successResponse("Product created successfully.", data=product_data)

    @staticmethod
    def update(data, request, product_id):
        with transaction.atomic():
            branch_data = ProductService.branchDataFromPayload(data)
            data = ProductService.masterDataFromPayload(data)
            if data.get("barcode") == "":
                data["barcode"] = None

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
            if data.get("unit_group_id"):
                unit_group = commonQuery.findOneRecord(
                    UnitGroup, data["unit_group_id"], request=request, tenant_config=True
                )
                if unit_group is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
                data["unit_group_id"] = unit_group["id"]
            if data.get("slug") is not None or data.get("name") is not None:
                data["slug"] = buildSlug(
                    Product,
                    data.get("name") or product["name"],
                    data.get("slug") or product["slug"],
                    request,
                    exclude_id=product["id"],
                )
            product_data = commonQuery.updateRecordById(Product, product_id, data, request=request, tenant_config=True)
            if product_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
            if branch_data:
                product_branch = commonQuery.findOneRecord(
                    ProductBranch,
                    {"product_id": product_id},
                    request=request,
                    tenant_config=True,
                )
                if product_branch:
                    commonQuery.updateRecordById(
                        ProductBranch,
                        product_branch["id"],
                        branch_data,
                        request=request,
                        tenant_config=True,
                    )
                else:
                    commonQuery.createRecord(
                        ProductBranch,
                        {
                            **branch_data,
                            "product_id": product_id,
                        },
                        request=request,
                        tenant_config=True,
                    )
            product_data = ProductService.attachBranchData(product_data, request)
            product_data["category_name"] = None
            product_data["brand_name"] = None
            product_data["tax_group_name"] = None
            product_data["unit_name"] = None
            product_data["unit_group_name"] = None
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
            if product_data.get("unit_group_id"):
                unit_group = commonQuery.findOneRecord(
                    UnitGroup,
                    product_data["unit_group_id"],
                    options={"attributes": ["name"]},
                    request=request,
                    tenant_config=True,
                )
                product_data["unit_group_name"] = unit_group["name"] if unit_group else None
            product_data["variants_count"] = Product.objects.get(id=product_id).variants.exclude(status=2).count()
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
                "slug",
                "image",
                "weight",
                "product_type",
                "is_tax_inclusive",
                "track_stock",
                "allow_decimal_qty",
                "expiry_tracking_enabled",
                "category_id",
                "brand_id",
                "unit_id",
                "unit_group_id",
                "tax_group_id",
                "status",
            ],
        }
        result = commonQuery.fetchPaginatedData(Product, data, fieldConfig, options, request=request, tenant_config=True)
        result["items"] = [ProductService.attachBranchData(item, request) for item in result["items"]]
        return successResponse("Products retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Product,
            {},
            {"attributes": ["id", "name", "sku", "barcode"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        data = [ProductService.attachBranchData(item, request) for item in data]
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
        product_data = ProductService.attachBranchData(product_data, request)
        product_data["category_name"] = None
        product_data["brand_name"] = None
        product_data["tax_group_name"] = None
        product_data["unit_name"] = None
        product_data["unit_group_name"] = None
        if product.get("category_id"):
            category = commonQuery.findOneRecord(
                Category,
                product["category_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            product_data["category_name"] = category["name"] if category else None
        if product.get("brand_id"):
            brand = commonQuery.findOneRecord(
                Brand,
                product["brand_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            product_data["brand_name"] = brand["name"] if brand else None
        if product.get("tax_group_id"):
            tax_group = commonQuery.findOneRecord(
                TaxGroup,
                product["tax_group_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            product_data["tax_group_name"] = tax_group["name"] if tax_group else None
        if product.get("unit_id"):
            unit = commonQuery.findOneRecord(
                Unit,
                product["unit_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            product_data["unit_name"] = unit["name"] if unit else None
        if product.get("unit_group_id"):
            unit_group = commonQuery.findOneRecord(
                UnitGroup,
                product["unit_group_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            product_data["unit_group_name"] = unit_group["name"] if unit_group else None
        product_data["variants_count"] = Product.objects.get(id=product_id).variants.exclude(status=2).count()
        return successResponse("Product retrieved successfully.", data=product_data)


class ProductVariantService:
    BRANCH_FIELDS = [
        "purchase_price",
        "selling_price",
        "mrp",
        "wholesale_price",
        "current_stock",
        "opening_stock",
        "min_stock",
        "max_stock",
        "reorder_level",
        "stock_alert_enabled",
    ]

    @staticmethod
    def branchDataFromPayload(data):
        return {field: data[field] for field in ProductVariantService.BRANCH_FIELDS if field in data}

    @staticmethod
    def masterDataFromPayload(data):
        return {key: value for key, value in data.items() if key not in ProductVariantService.BRANCH_FIELDS}

    @staticmethod
    def attachBranchData(variant_data, request):
        variant_branch = commonQuery.findOneRecord(
            ProductVariantBranch,
            {"variant_id": variant_data["id"]},
            request=request,
            tenant_config=True,
        )
        for field in ProductVariantService.BRANCH_FIELDS:
            variant_data[field] = variant_branch.get(field) if variant_branch else 0
        if not variant_branch:
            variant_data["stock_alert_enabled"] = True
        return variant_data

    @staticmethod
    def validateProduct(product_id, request):
        product = commonQuery.findOneRecord(Product, product_id, request=request, tenant_config=True)
        if product is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        return product

    @staticmethod
    def validateUnit(unit_id, request):
        if not unit_id:
            return None
        unit = commonQuery.findOneRecord(Unit, unit_id, request=request, tenant_config=True)
        if unit is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
        return unit

    @staticmethod
    def ensureUnique(data, request, exclude_id=None):
        if data.get("sku"):
            existing = commonQuery.findOneRecord(
                ProductVariant,
                {"sku": data["sku"]},
                request=request,
                tenant_config=True,
            )
            if existing and existing.get("id") != exclude_id:
                raise api_error(400, ErrorCodes.VALIDATION_ERROR, "SKU already exists.")
        if data.get("barcode"):
            existing = commonQuery.findOneRecord(
                ProductVariant,
                {"barcode": data["barcode"]},
                request=request,
                tenant_config=True,
            )
            if existing and existing.get("id") != exclude_id:
                raise api_error(400, ErrorCodes.VALIDATION_ERROR, "Barcode already exists.")

    @staticmethod
    def create(data, request):
        with transaction.atomic():
            branch_data = ProductVariantService.branchDataFromPayload(data)
            data = ProductVariantService.masterDataFromPayload(data)
            if data.get("barcode") == "":
                data["barcode"] = None

            product = ProductVariantService.validateProduct(data.get("product_id"), request)
            unit = ProductVariantService.validateUnit(data.get("unit_id"), request)
            ProductVariantService.ensureUnique(data, request)

            variant = commonQuery.createRecord(
                ProductVariant,
                {
                    **data,
                    "product_id": product["id"],
                    "unit_id": unit["id"] if unit else None,
                },
                request=request,
                tenant_config=True,
            )
            commonQuery.createRecord(
                ProductVariantBranch,
                {
                    **branch_data,
                    "variant_id": variant["id"],
                },
                request=request,
                tenant_config=True,
            )
            variant_data = ProductVariantService.attachBranchData(dict(variant), request)
            variant_data["product_name"] = product["name"]
            variant_data["unit_name"] = unit["name"] if unit else None
            return successResponse("Product variant created successfully.", data=variant_data)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["sku", True, True], ["barcode", True, True]]
        options = {
            "attributes": ["id", "product_id", "unit_id", "name", "sku", "barcode", "status"],
        }
        result = commonQuery.fetchPaginatedData(ProductVariant, data, fieldConfig, options, request=request, tenant_config=True)
        result["items"] = [ProductVariantService.attachBranchData(item, request) for item in result["items"]]
        return successResponse("Product variants retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            ProductVariant,
            {},
            {"attributes": ["id", "product_id", "name", "sku", "barcode"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        data = [ProductVariantService.attachBranchData(item, request) for item in data]
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(ProductVariant, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product variant not found.")
        return successResponse("Product variants deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            ProductVariant,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product variant not found.")
        return successResponse("Product variant status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(variant_id, request):
        variant = commonQuery.findOneRecord(ProductVariant, variant_id, request=request, tenant_config=True)
        if variant is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product variant not found.")
        variant_data = ProductVariantService.attachBranchData(dict(variant), request)
        variant_data["product_name"] = None
        variant_data["unit_name"] = None
        if variant.get("product_id"):
            product = commonQuery.findOneRecord(
                Product,
                variant["product_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            variant_data["product_name"] = product["name"] if product else None
        if variant.get("unit_id"):
            unit = commonQuery.findOneRecord(
                Unit,
                variant["unit_id"],
                options={"attributes": ["name"]},
                request=request,
                tenant_config=True,
            )
            variant_data["unit_name"] = unit["name"] if unit else None
        return successResponse("Product variant retrieved successfully.", data=variant_data)

    @staticmethod
    def update(data, request, variant_id):
        with transaction.atomic():
            branch_data = ProductVariantService.branchDataFromPayload(data)
            data = ProductVariantService.masterDataFromPayload(data)
            if data.get("barcode") == "":
                data["barcode"] = None

            variant = commonQuery.findOneRecord(ProductVariant, variant_id, request=request, tenant_config=True)
            if variant is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product variant not found.")
            if data.get("product_id"):
                product = ProductVariantService.validateProduct(data.get("product_id"), request)
                data["product_id"] = product["id"]
            if data.get("unit_id"):
                unit = ProductVariantService.validateUnit(data.get("unit_id"), request)
                data["unit_id"] = unit["id"]
            ProductVariantService.ensureUnique(data, request, exclude_id=variant["id"])

            variant_data = commonQuery.updateRecordById(
                ProductVariant,
                variant_id,
                data,
                request=request,
                tenant_config=True,
            )
            if variant_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product variant not found.")
            if branch_data:
                variant_branch = commonQuery.findOneRecord(
                    ProductVariantBranch,
                    {"variant_id": variant_id},
                    request=request,
                    tenant_config=True,
                )
                if variant_branch:
                    commonQuery.updateRecordById(
                        ProductVariantBranch,
                        variant_branch["id"],
                        branch_data,
                        request=request,
                        tenant_config=True,
                    )
                else:
                    commonQuery.createRecord(
                        ProductVariantBranch,
                        {
                            **branch_data,
                            "variant_id": variant_id,
                        },
                        request=request,
                        tenant_config=True,
                    )
            variant_data = ProductVariantService.attachBranchData(variant_data, request)
            return successResponse("Product variant updated successfully.", data=variant_data)


class ProductVariantBranchService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            variant = commonQuery.findOneRecord(
                ProductVariant,
                data.get("variant_id"),
                request=request,
                tenant_config=True,
            )
            if variant is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product variant not found.")
            existing = commonQuery.findOneRecord(
                ProductVariantBranch,
                {"variant_id": variant["id"]},
                request=request,
                tenant_config=True,
            )
            if existing:
                branch_data = commonQuery.updateRecordById(
                    ProductVariantBranch,
                    existing["id"],
                    data,
                    request=request,
                    tenant_config=True,
                )
                return successResponse("Product variant branch updated successfully.", data=branch_data)
            branch_data = commonQuery.createRecord(
                ProductVariantBranch,
                {
                    **data,
                    "variant_id": variant["id"],
                },
                request=request,
                tenant_config=True,
            )
            return successResponse("Product variant branch created successfully.", data=branch_data)

    @staticmethod
    def update(data, request, branch_setting_id):
        with transaction.atomic():
            if data.get("variant_id"):
                variant = commonQuery.findOneRecord(
                    ProductVariant,
                    data.get("variant_id"),
                    request=request,
                    tenant_config=True,
                )
                if variant is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Product variant not found.")
                data["variant_id"] = variant["id"]
            branch_data = commonQuery.updateRecordById(
                ProductVariantBranch,
                branch_setting_id,
                data,
                request=request,
                tenant_config=True,
            )
            if branch_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product variant branch not found.")
            return successResponse("Product variant branch updated successfully.", data=branch_data)
