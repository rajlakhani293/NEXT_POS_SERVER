# type: ignore
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.catalog.models import (
    Category,
    Product,
    ProductGallery,
    ProductHistory,
    ProductHistoryCombined,
    ProductSubItem,
    ProductTax,
    ProductUnitQuantity,
    ScaleRange,
    Tax,
    TaxGroup,
    Unit,
    UnitGroup,
)
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.domainActions import DomainActionService
from apps.common.helpers import buildSku, buildUniqueValue, decimalValue, saveProductImage, serializeModelInstance, validateTenantRelationId, validateUniqueFields
from apps.common.responses import successResponse
from apps.common.tenantDefaults import DEFAULT_SCALE_RANGES


def _emptyToNone(data, fields):
    for field in fields:
        if data.get(field) == "":
            data[field] = None
    return data


def _relationName(model, record_id, request):
    if not record_id:
        return None
    row = commonQuery.findOneRecord(
        model,
        record_id,
        options={"attributes": ["name"]},
        request=request,
        tenant_config=True,
    )
    return row["name"] if row else None


def _buildBarcode(request, exclude_id=None):
    raw = timezone.now().strftime("%y%m%d%H%M%S%f")[:13]
    return buildUniqueValue(Product, request, "barcode", raw, exclude_id=exclude_id)


def _normalizeProductPayload(data):
    return data


class ScaleRangeService:
    @staticmethod
    def validateRange(data, request, scale_range_id=None):
        range_start = data.get("range_start")
        range_end = data.get("range_end")
        next_scale_plu = data.get("next_scale_plu")
        if range_start is None or range_end is None or next_scale_plu is None:
            existing = None
            if scale_range_id:
                existing = commonQuery.branchScopedQueryset(ScaleRange, {"id": scale_range_id}, request).exclude(status=2).first()
            range_start = range_start if range_start is not None else getattr(existing, "range_start", None)
            range_end = range_end if range_end is not None else getattr(existing, "range_end", None)
            next_scale_plu = next_scale_plu if next_scale_plu is not None else getattr(existing, "next_scale_plu", None)
        if range_start is None or range_end is None or next_scale_plu is None:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Range start, range end, and next PLU are required.")
        if range_start >= range_end:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "The range start must be less than the range end.")
        if next_scale_plu < range_start or next_scale_plu > range_end:
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"The next PLU ({next_scale_plu}) must be within the range {range_start}-{range_end}.")
        overlap = (
            commonQuery.branchScopedQueryset(ScaleRange, {}, request)
            .exclude(status=2)
            .filter(
                Q(range_start__lte=range_start, range_end__gte=range_start)
                | Q(range_start__lte=range_end, range_end__gte=range_end)
                | Q(range_start__gte=range_start, range_end__lte=range_end)
            )
        )
        if scale_range_id:
            overlap = overlap.exclude(id=scale_range_id)
        overlapping_range = overlap.first()
        if overlapping_range:
            raise api_error(
                400,
                ErrorCodes.BAD_REQUEST,
                f"The PLU range {range_start}-{range_end} overlaps with an existing range \"{overlapping_range.name}\" ({overlapping_range.range_start}-{overlapping_range.range_end}).",
            )

    @staticmethod
    def ensureDefaultScaleRanges(company, branch):
        ranges = []
        for name, range_start, range_end, next_scale_plu, description in DEFAULT_SCALE_RANGES:
            scale_range, created = commonQuery.getOrCreateRecord(
                ScaleRange,
                {"company_id": company.id, "branch_id": branch.id, "name": name},
                defaults={
                    "range_start": range_start,
                    "range_end": range_end,
                    "next_scale_plu": next_scale_plu,
                    "description": description,
                },
                tenant_config={},
                return_plain=False,
            )
            update_fields = []
            if created is False and scale_range.range_start != range_start:
                scale_range.range_start = range_start
                update_fields.append("range_start")
            if created is False and scale_range.range_end != range_end:
                scale_range.range_end = range_end
                update_fields.append("range_end")
            if created is False and scale_range.description != description:
                scale_range.description = description
                update_fields.append("description")
            if update_fields:
                scale_range.save(update_fields=[*update_fields, "updated_at"])
            ranges.append(scale_range)
        return ranges

    @staticmethod
    def create(data, request):
        ScaleRangeService.validateRange(data, request)
        row = commonQuery.createRecord(ScaleRange, data, request=request, tenant_config=True)
        return successResponse("Scale range created successfully.", data=row)

    @staticmethod
    def update(scale_range_id, data, request):
        ScaleRangeService.validateRange(data, request, scale_range_id=scale_range_id)
        updated = commonQuery.updateRecordById(ScaleRange, scale_range_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Scale range not found.")
        return successResponse("Scale range updated successfully.", data=updated)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            ScaleRange,
            data,
            [["name", True, True], ["description", True, True]],
            {"attributes": ["id", "name", "range_start", "range_end", "next_scale_plu", "description", "status", "created_at"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Scale ranges retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        rows = commonQuery.findAllRecords(
            ScaleRange,
            {},
            {"attributes": ["id", "name", "range_start", "range_end", "next_scale_plu"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=rows)

    @staticmethod
    def getById(scale_range_id, request):
        row = commonQuery.findOneRecord(ScaleRange, scale_range_id, request=request, tenant_config=True)
        if row is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Scale range not found.")
        return successResponse("Scale range retrieved successfully.", data=row)

    @staticmethod
    def delete(data, request):
        ids = data.get("ids")
        id_list = ids if isinstance(ids, list) else [ids]
        ranges = list(commonQuery.branchScopedQueryset(ScaleRange, {"id__in": id_list}, request).exclude(status=2))
        for scale_range in ranges:
            if commonQuery.branchScopedQueryset(Category, {"scale_range_id": scale_range.id}, request).exclude(status=2).exists():
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Cannot delete this PLU range because it is being used by one or more categories.")
            if scale_range.getUsedCount() > 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Cannot delete this PLU range because {scale_range.getUsedCount()} product(s) are using PLU codes from this range.")
        count = commonQuery.softDeleteById(ScaleRange, ids, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Scale range not found.")
        return successResponse("Scale ranges deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(ScaleRange, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Scale range not found.")
        return successResponse("Scale range status updated successfully.", data={"updated_count": count, "status": status})


class CategoryService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            if data.get("parent_id"):
                data["parent_id"] = validateTenantRelationId(Category, data["parent_id"], request=request, label="Parent category")
            if data.get("scale_range_id"):
                data["scale_range_id"] = validateTenantRelationId(ScaleRange, data["scale_range_id"], request=request, label="Scale range")
            category = commonQuery.createRecord(Category, data, request=request, tenant_config=True)
            return successResponse("Category created successfully.", data=category)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["description", True, True]]
        options = {
            "attributes": [
                "id",
                "name",
                "parent_id",
                "parent__name",
                "media_id",
                "preview_url",
                "displays_on_pos",
                "scale_range_id",
                "scale_range__name",
                "total_items",
                "position",
                "description",
                "status",
                "user__username",
                "created_at",
            ],
        }
        result = commonQuery.fetchPaginatedData(Category, data, fieldConfig, options, request=request, tenant_config=True)
        for item in result["items"]:
            item["parent_name"] = item.pop("parent__name", None)
            item["scale_range_name"] = item.pop("scale_range__name", None)
            item["user_username"] = item.pop("user__username", None)
        return successResponse("Categories retrieved successfully.", data=result)

    @staticmethod
    def getSource(id=None, parent=False, request=None):
        if id:
            category = commonQuery.findOneRecord(Category, id, request=request, tenant_config=True)
            if category is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to find the category using the provided identifier")
            return successResponse("Category retrieved successfully.", data=category)
        filters = {"parent_id": None} if parent else {}
        rows = commonQuery.findAllRecords(
            Category,
            filters,
            {"attributes": ["id", "name", "parent_id", "description", "media_id", "preview_url", "displays_on_pos", "scale_range_id", "total_items", "position", "status"], "order": ["position", "name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Categories retrieved successfully.", data=rows)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Category,
            {},
            {"attributes": ["id", "name", "parent_id"], "order": ["position", "name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getById(category_id, request):
        category = commonQuery.findOneRecord(Category, category_id, request=request, tenant_config=True)
        if category is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
        category = dict(category)
        category["parent_name"] = _relationName(Category, category.get("parent_id"), request)
        category["scale_range_name"] = _relationName(ScaleRange, category.get("scale_range_id"), request)
        return successResponse("Category retrieved successfully.", data=category)

    @staticmethod
    def update(data, request, category_id):
        with transaction.atomic():
            category = commonQuery.findOneRecord(Category, category_id, request=request, tenant_config=True)
            if category is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
            if data.get("parent_id"):
                data["parent_id"] = validateTenantRelationId(Category, data["parent_id"], request=request, label="Parent category")
            if data.get("scale_range_id"):
                data["scale_range_id"] = validateTenantRelationId(ScaleRange, data["scale_range_id"], request=request, label="Scale range")
            updated = commonQuery.updateRecordById(Category, category_id, data, request=request, tenant_config=True)
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
            return successResponse("Category updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        ids = data.get("ids")
        id_list = ids if isinstance(ids, list) else [ids]
        if commonQuery.branchScopedQueryset(Category, {"parent_id__in": id_list}, request).exclude(status=2).exists():
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Can't delete a category having sub categories linked to it.")
        count = commonQuery.softDeleteById(Category, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
        return successResponse("Categories deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(Category, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
        return successResponse("Category status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def computeProducts(category_id, request):
        category = commonQuery.branchScopedQueryset(Category, {"id": category_id}, request).exclude(status=2).first()
        if category is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Category not found.")
        total_items = commonQuery.branchScopedQueryset(
            Product,
            {"category_id": category.id, "status__in": [0, 1]},
            request,
        ).count()
        category.total_items = total_items
        category.save(update_fields=["total_items", "updated_at"])
        return successResponse("Category products recomputed successfully.", data={"category_id": category.id, "total_items": total_items})

    @staticmethod
    def reorderCategories(data, request):
        items = (data or {}).get("items") or []
        for index, item in enumerate(items):
            category_id = item.get("id") if isinstance(item, dict) else item
            commonQuery.branchScopedQueryset(Category, {"id": category_id}, request).exclude(status=2).update(position=index)
        return successResponse("Categories have been successfully reordered.")

    @staticmethod
    def getProducts(category_id, request, variations_only=False):
        validateTenantRelationId(Category, category_id, request=request, label="Category", tenant_config=True)
        queryset = commonQuery.branchScopedQueryset(Product, {"category_id": category_id}, request).exclude(status=2).filter(product_type__in=["variation"] if variations_only else ["product", "variation"])
        queryset = queryset.filter(status=0).select_related("category", "tax_group", "unit_group", "parent").prefetch_related("unit_quantities", "gallery", "variations")
        return successResponse("Category products retrieved successfully.", data=[ProductService.serializeProduct(product, request) for product in queryset])

    @staticmethod
    def jobHandlers():
        return {
            "compute_category_products": lambda data, job: CategoryService.computeProducts(
                data.get("category_id") or data.get("product_category_id"),
                ProductStockService.requestFromJob(job),
            ),
        }

    @staticmethod
    def getPOSCategories(request, parent_id=None):
        from apps.catalog.models import Product
        from apps.common.helpers import serializeModelInstance

        # Clean/normalize parent_id
        if parent_id in ["0", 0, "", "null", "None"]:
            parent_id = None
        else:
            try:
                parent_id = int(parent_id)
            except (ValueError, TypeError):
                parent_id = None

        # 1. Pinned products (always returned)
        pinned_qs = commonQuery.branchScopedQueryset(
            Product,
            {"pinned": True, "status": 0},
            request=request
        ).prefetch_related("gallery", "tax_group", "tax_group__taxes", "unit_quantities", "unit_quantities__unit")

        pinned_products = []
        for p in pinned_qs:
            p_data = serializeModelInstance(p)
            p_data["galleries"] = list(p.gallery.all().values())
            p_data["unit_quantities"] = []
            for uq in p.unit_quantities.filter(status=0, visible=True):
                uq_data = serializeModelInstance(uq)
                if uq.unit:
                    uq_data["unit"] = serializeModelInstance(uq.unit)
                p_data["unit_quantities"].append(uq_data)
            pinned_products.append(p_data)

        # 2. Categories query
        cat_filters = {"displays_on_pos": True, "status": 0}
        if parent_id is None:
            cat_filters["parent_id"] = None
        else:
            cat_filters["parent_id"] = parent_id

        from apps.settings.services import OptionSettingService
        from django.db.models import Count, Q
        hide_empty = OptionSettingService.getOptionValue(request.user.company, request.user.branch, "hide_empty_categories", False)

        categories_qs = commonQuery.branchScopedQueryset(
            Category,
            cat_filters,
            request=request
        )
        if hide_empty:
            categories_qs = categories_qs.annotate(
                prod_count=Count("products", filter=Q(products__status=0)),
                sub_count=Count("children", filter=Q(children__status=0))
            ).filter(Q(prod_count__gt=0) | Q(sub_count__gt=0))

        categories_qs = categories_qs.order_by("position", "name")
        categories_data = [serializeModelInstance(cat) for cat in categories_qs]

        # 3. Current and previous category
        current_category = None
        previous_category = None
        products_data = []

        if parent_id is not None:
            curr_cat_obj = commonQuery.branchScopedQueryset(
                Category,
                {"id": parent_id, "status": 0},
                request=request
            ).first()
            if curr_cat_obj:
                current_category = serializeModelInstance(curr_cat_obj)
                if curr_cat_obj.parent:
                    previous_category = serializeModelInstance(curr_cat_obj.parent)

                # 4. Products query for this category
                products_qs = commonQuery.branchScopedQueryset(
                    Product,
                    {"category_id": parent_id, "status": 0},
                    request=request
                ).prefetch_related("gallery", "tax_group", "tax_group__taxes", "unit_quantities", "unit_quantities__unit").order_by("position", "created_at")
                
                for p in products_qs:
                    p_data = serializeModelInstance(p)
                    p_data["galleries"] = list(p.gallery.all().values())
                    p_data["unit_quantities"] = []
                    for uq in p.unit_quantities.filter(status=0, visible=True):
                        uq_data = serializeModelInstance(uq)
                        if uq.unit:
                            uq_data["unit"] = serializeModelInstance(uq.unit)
                        p_data["unit_quantities"].append(uq_data)
                    products_data.append(p_data)

        return successResponse("POS Categories retrieved successfully.", data={
            "products": products_data,
            "categories": categories_data,
            "previousCategory": previous_category,
            "currentCategory": current_category,
            "pinnedProducts": pinned_products,
        })



class UnitGroupService:
    @staticmethod
    def create(data, request):
        unit_group = commonQuery.createRecord(UnitGroup, data, request=request, tenant_config=True)
        return successResponse("Unit group created successfully.", data=unit_group)

    @staticmethod
    def update(data, request, unit_group_id):
        updated = commonQuery.updateRecordById(UnitGroup, unit_group_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
        return successResponse("Unit group updated successfully.", data=updated)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["description", True, True]]
        options = {"attributes": ["id", "name", "description", "status"]}
        result = commonQuery.fetchPaginatedData(UnitGroup, data, fieldConfig, options, request=request, tenant_config=True)
        return successResponse("Unit groups retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(UnitGroup, {}, {"attributes": ["id", "name"], "order": ["name"]}, request=request, tenant_config=True)
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getSource(group_id=None, request=None):
        if group_id:
            group = commonQuery.findOneRecord(
                UnitGroup,
                group_id,
                options={"include": [{"path": "units", "fields": ["id", "name", "identifier", "description", "group_id", "value", "base_unit", "status"]}]},
                request=request,
                tenant_config=True,
            )
            if group is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to find the unit group to which this unit is attached.")
            return successResponse("Unit group retrieved successfully.", data=group)
        groups = commonQuery.findAllRecords(
            UnitGroup,
            {},
            {"attributes": ["id", "name", "description", "status"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Unit groups retrieved successfully.", data=groups)

    @staticmethod
    def getGroupUnits(group_id, request):
        validateTenantRelationId(UnitGroup, group_id, request=request, label="Unit group", tenant_config=True)
        units = commonQuery.findAllRecords(
            Unit,
            {"group_id": group_id},
            {"attributes": ["id", "name", "identifier", "description", "group_id", "value", "base_unit", "status"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Group units retrieved successfully.", data=units)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(UnitGroup, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
        return successResponse("Unit groups deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(UnitGroup, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
        return successResponse("Unit group status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(unit_group_id, request):
        unit_group = commonQuery.findOneRecord(UnitGroup, unit_group_id, request=request, tenant_config=True)
        if unit_group is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit group not found.")
        unit_group = dict(unit_group)
        unit_group["units_count"] = commonQuery.countRecords(Unit, {"group_id": unit_group_id}, request=request, tenant_config=True)
        return successResponse("Unit group retrieved successfully.", data=unit_group)


class UnitService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            data["group_id"] = validateTenantRelationId(UnitGroup, data["group_id"], request=request, label="Unit group", tenant_config=True)
            validateUniqueFields(
                Unit,
                {"identifier": data.get("identifier")},
                request=request,
                scope="branch",
                status_in=(0, 1),
                case_insensitive=["identifier"],
                messages={"identifier": "Unit identifier already exists."},
            )
            if data.get("base_unit"):
                commonQuery.branchScopedQueryset(
                    Unit,
                    {"group_id": data["group_id"], "status__in": [0, 1]},
                    request,
                ).update(base_unit=False)
            unit = commonQuery.createRecord(Unit, data, request=request, tenant_config=True)
            unit["group_name"] = _relationName(UnitGroup, unit.get("group_id"), request)
            return successResponse("Unit created successfully.", data=unit)

    @staticmethod
    def update(data, request, unit_id):
        with transaction.atomic():
            unit = commonQuery.findOneRecord(Unit, unit_id, request=request, tenant_config=True)
            if unit is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
            if data.get("group_id"):
                data["group_id"] = validateTenantRelationId(UnitGroup, data["group_id"], request=request, label="Unit group", tenant_config=True)
            if "identifier" in data:
                validateUniqueFields(
                    Unit,
                    {"identifier": data.get("identifier")},
                    request=request,
                    scope="branch",
                    exclude_id=unit_id,
                    status_in=(0, 1),
                    case_insensitive=["identifier"],
                    messages={"identifier": "Unit identifier already exists."},
                )
            if data.get("base_unit"):
                commonQuery.branchScopedQueryset(
                    Unit,
                    {"group_id": data.get("group_id") or unit["group_id"], "status__in": [0, 1]},
                    request,
                ).exclude(id=unit_id).update(base_unit=False)
            updated = commonQuery.updateRecordById(Unit, unit_id, data, request=request, tenant_config=True)
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
            updated["group_name"] = _relationName(UnitGroup, updated.get("group_id"), request)
            return successResponse("Unit updated successfully.", data=updated)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["identifier", True, True]]
        options = {"attributes": ["id", "name", "identifier", "description", "value", "preview_url", "base_unit", "group_id", "group__name", "status", "user__username", "created_at"]}
        result = commonQuery.fetchPaginatedData(Unit, data, fieldConfig, options, request=request, tenant_config=True)
        for item in result["items"]:
            item["group_name"] = item.pop("group__name", None)
            item["user_username"] = item.pop("user__username", None)
        return successResponse("Units retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Unit,
            {},
            {"attributes": ["id", "name", "identifier", "group_id", "base_unit"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getSource(unit_id=None, request=None):
        if unit_id:
            unit = commonQuery.findOneRecord(Unit, unit_id, request=request, tenant_config=True)
            if unit is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to find the Unit using the provided id.")
            return successResponse("Unit retrieved successfully.", data=unit)
        units = commonQuery.findAllRecords(
            Unit,
            {},
            {"attributes": ["id", "name", "identifier", "description", "group_id", "value", "preview_url", "base_unit", "status"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Units retrieved successfully.", data=units)

    @staticmethod
    def getSiblingUnits(unit_id, request):
        unit = commonQuery.branchScopedQueryset(Unit, {"id": unit_id}, request).exclude(status=2).first()
        if unit is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to find the Unit using the provided id.")
        siblings = commonQuery.findAllRecords(
            Unit,
            {"group_id": unit.group_id},
            {"attributes": ["id", "name", "identifier", "description", "group_id", "value", "base_unit", "status"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Sibling units retrieved successfully.", data=[item for item in siblings if item["id"] != unit.id])

    @staticmethod
    def getUnitParentGroup(unit_id, request):
        unit = commonQuery.branchScopedQueryset(Unit, {"id": unit_id}, request).exclude(status=2).select_related("group").first()
        if unit is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to find the Unit using the provided id.")
        return successResponse("Unit group retrieved successfully.", data=serializeModelInstance(unit.group))

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Unit, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
        return successResponse("Units deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(Unit, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
        return successResponse("Unit status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(unit_id, request):
        unit = commonQuery.findOneRecord(Unit, unit_id, request=request, tenant_config=True)
        if unit is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
        unit = dict(unit)
        unit["group_name"] = _relationName(UnitGroup, unit.get("group_id"), request)
        return successResponse("Unit retrieved successfully.", data=unit)


class TaxGroupService:
    @staticmethod
    def create(data, request):
        tax_group = commonQuery.createRecord(TaxGroup, data, request=request, tenant_config=True)
        return successResponse("Tax group created successfully.", data=tax_group)

    @staticmethod
    def update(data, request, tax_group_id):
        updated = commonQuery.updateRecordById(TaxGroup, tax_group_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
        return successResponse("Tax group updated successfully.", data=updated)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["description", True, True]]
        options = {"attributes": ["id", "name", "description", "status", "created_at", "user__username"]}
        result = commonQuery.fetchPaginatedData(TaxGroup, data, fieldConfig, options, request=request, tenant_config=True)
        for item in result["items"]:
            item["user_username"] = item.pop("user__username", None)
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
            total_rate = 0
            for tax in taxes:
                if tax.get("status") != 2:
                    total_rate += float(tax.get("rate") or 0)
                    active_taxes.append({"id": tax.get("id"), "name": tax.get("name"), "rate": tax.get("rate")})
            group["rate"] = total_rate
            group["taxes"] = active_taxes
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getSource(tax_group_id=None, request=None):
        if tax_group_id:
            group = commonQuery.findOneRecord(
                TaxGroup,
                tax_group_id,
                options={"include": [{"path": "taxes", "fields": ["id", "name", "description", "rate", "tax_group_id", "status"]}]},
                request=request,
                tenant_config=True,
            )
            if group is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, f"Unable to retrieve the requested tax group using the provided identifier \"{tax_group_id}\".")
            taxes = []
            for tax in group.get("taxes") or []:
                item = dict(tax)
                item["tax_id"] = item.pop("id")
                taxes.append(item)
            group["taxes"] = taxes
            return successResponse("Tax group retrieved successfully.", data=group)
        groups = commonQuery.findAllRecords(
            TaxGroup,
            {},
            {
                "attributes": ["id", "name", "description", "status"],
                "include": [{"path": "taxes", "fields": ["id", "name", "description", "rate", "tax_group_id", "status"]}],
                "order": ["name"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Tax groups retrieved successfully.", data=groups)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(TaxGroup, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
        return successResponse("Tax groups deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(TaxGroup, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
        return successResponse("Tax group status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(tax_group_id, request):
        tax_group = commonQuery.findOneRecord(TaxGroup, tax_group_id, request=request, tenant_config=True)
        if tax_group is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax group not found.")
        tax_group = dict(tax_group)
        tax_group["taxes_count"] = commonQuery.countRecords(Tax, {"tax_group_id": tax_group_id}, request=request, tenant_config=True)
        return successResponse("Tax group retrieved successfully.", data=tax_group)


class TaxService:
    @staticmethod
    def create(data, request):
        data["tax_group_id"] = validateTenantRelationId(TaxGroup, data["tax_group_id"], request=request, label="Tax group", tenant_config=True)
        tax = commonQuery.createRecord(Tax, data, request=request, tenant_config=True)
        return successResponse("Tax created successfully.", data=tax)

    @staticmethod
    def update(data, request, tax_id):
        if data.get("tax_group_id"):
            data["tax_group_id"] = validateTenantRelationId(TaxGroup, data["tax_group_id"], request=request, label="Tax group", tenant_config=True)
        updated = commonQuery.updateRecordById(Tax, tax_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax not found.")
        return successResponse("Tax updated successfully.", data=updated)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["rate", False, True]]
        options = {
            "attributes": [
                "id",
                "name",
                "description",
                "rate",
                "tax_group_id",
                "tax_group__name",
                "status",
                "created_at",
                "user__username",
            ]
        }
        result = commonQuery.fetchPaginatedData(Tax, data, fieldConfig, options, request=request, tenant_config=True)
        for item in result["items"]:
            item["parent_name"] = item.get("tax_group__name")
            item["tax_group_name"] = item.pop("tax_group__name", None)
            item["user_username"] = item.pop("user__username", None)
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
        for item in data:
            item["tax_group_name"] = item.pop("tax_group__name", None)
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getSource(tax_id=None, request=None):
        if tax_id:
            tax = commonQuery.findOneRecord(Tax, tax_id, request=request, tenant_config=True)
            if tax is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to find the requested product tax using the provided id")
            return successResponse("Tax retrieved successfully.", data=tax)
        taxes = commonQuery.findAllRecords(
            Tax,
            {},
            {"attributes": ["id", "name", "description", "rate", "tax_group_id", "status"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Taxes retrieved successfully.", data=taxes)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Tax, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax not found.")
        return successResponse("Taxes deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(Tax, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax not found.")
        return successResponse("Tax status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(tax_id, request):
        tax = commonQuery.findOneRecord(Tax, tax_id, request=request, tenant_config=True)
        if tax is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Tax not found.")
        return successResponse("Tax retrieved successfully.", data=tax)


class ProductService:
    @staticmethod
    def serializeProduct(product, request, include_relations=True):
        data = serializeModelInstance(product)
        data = ProductService.attachDisplayData(dict(data), request)
        if include_relations:
            data["unit_quantities"] = [
                ProductUnitQuantityService.attachDisplayData(serializeModelInstance(unit_quantity))
                for unit_quantity in product.unit_quantities.filter(status__in=[0, 1]).select_related("unit", "convert_unit").order_by("id")
            ]
            data["gallery"] = list(product.gallery.filter(status__in=[0, 1]).values("id", "name", "media_id", "url", "order", "featured", "status"))
            data["variations"] = [
                ProductService.serializeProduct(variation, request, include_relations=False)
                for variation in product.variations.filter(status__in=[0, 1]).order_by("position", "name")
            ]
            if product.tax_group_id:
                data["tax_group"] = serializeModelInstance(product.tax_group)
                data["taxes"] = list(product.tax_group.taxes.exclude(status=2).values("id", "name", "rate", "status"))
        return data

    @staticmethod
    def attachDisplayData(product_data, request):
        product_data["category_name"] = _relationName(Category, product_data.get("category_id"), request)
        product_data["tax_group_name"] = _relationName(TaxGroup, product_data.get("tax_group_id"), request)
        product_data["unit_group_name"] = _relationName(UnitGroup, product_data.get("unit_group_id"), request)
        parent_id = product_data.get("parent_id")
        product_data["parent_name"] = _relationName(Product, parent_id, request) if parent_id else None
        return product_data

    @staticmethod
    def create(data, request, image=None):
        with transaction.atomic():
            data = _normalizeProductPayload(data)
            _emptyToNone(data, ["sku", "barcode", "barcode_type", "tax_type"])
            if data.get("sku"):
                data["sku"] = buildSku(Product, data.get("name"), data.get("sku"), request)
            else:
                data["sku"] = buildSku(Product, data.get("name"), None, request)
            if data.get("barcode"):
                validateUniqueFields(
                    Product,
                    {"barcode": data.get("barcode")},
                    request=request,
                    scope="branch",
                    status_in=(0, 1),
                    messages={"barcode": "Barcode already exists on another product."},
                )
            else:
                data["barcode"] = _buildBarcode(request)
            if not data.get("barcode_type"):
                data["barcode_type"] = "ean13"
            for field, model, label in [
                ("category_id", Category, "Category"),
                ("tax_group_id", TaxGroup, "Tax group"),
                ("parent_id", Product, "Parent product"),
                ("unit_group_id", UnitGroup, "Unit group"),
            ]:
                if data.get(field):
                    data[field] = validateTenantRelationId(model, data[field], request=request, label=label, tenant_config=True)

            image_url = saveProductImage(image, request)
            product = commonQuery.createRecord(Product, data, request=request, tenant_config=True)
            if image_url:
                commonQuery.createRecord(
                    ProductGallery,
                    {"product_id": product["id"], "url": image_url, "featured": True},
                    request=request,
                    tenant_config=True,
                )
            DomainActionService.afterProductCreated(product, request)
            product = ProductService.attachDisplayData(dict(product), request)
            return successResponse("Product created successfully.", data=product)

    @staticmethod
    def update(data, request, product_id, image=None):
        with transaction.atomic():
            data = _normalizeProductPayload(data)
            product = commonQuery.findOneRecord(Product, product_id, request=request, tenant_config=True)
            if product is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
            _emptyToNone(data, ["sku", "barcode", "barcode_type", "tax_type"])
            for field, model, label in [
                ("category_id", Category, "Category"),
                ("tax_group_id", TaxGroup, "Tax group"),
                ("parent_id", Product, "Parent product"),
                ("unit_group_id", UnitGroup, "Unit group"),
            ]:
                if data.get(field):
                    data[field] = validateTenantRelationId(model, data[field], request=request, label=label, tenant_config=True)
            if "sku" in data and data.get("sku"):
                data["sku"] = buildSku(Product, data.get("name") or product["name"], data.get("sku"), request, exclude_id=product["id"])
            if "barcode" in data and data.get("barcode"):
                validateUniqueFields(
                    Product,
                    {"barcode": data.get("barcode")},
                    request=request,
                    scope="branch",
                    exclude_id=product["id"],
                    status_in=(0, 1),
                    messages={"barcode": "Barcode already exists on another product."},
                )
            elif "barcode" in data:
                data["barcode"] = _buildBarcode(request, exclude_id=product["id"])
            if "barcode_type" in data and not data.get("barcode_type"):
                data["barcode_type"] = "ean13"

            updated = commonQuery.updateRecordById(Product, product_id, data, request=request, tenant_config=True)
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
            image_url = saveProductImage(image, request)
            if image_url:
                commonQuery.branchScopedQueryset(
                    ProductGallery,
                    {"product_id": product_id, "featured": True, "status__in": [0, 1]},
                    request,
                ).update(featured=False)
                commonQuery.createRecord(
                    ProductGallery,
                    {"product_id": product_id, "url": image_url, "featured": True},
                    request=request,
                    tenant_config=True,
                )
            DomainActionService.afterProductUpdated(product, updated, request)
            old_category_id = product.get("category_id")
            new_category_id = updated.get("category_id")
            if old_category_id and old_category_id != new_category_id:
                CategoryService.computeProducts(old_category_id, request)
            if new_category_id:
                CategoryService.computeProducts(new_category_id, request)
            updated = ProductService.attachDisplayData(dict(updated), request)
            return successResponse("Product updated successfully.", data=updated)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["sku", True, True], ["barcode", True, True], ["product_type", False, True]]
        options = {
            "attributes": [
                "id",
                "name",
                "tax_type",
                "tax_group_id",
                "tax_group__name",
                "tax_value",
                "product_type",
                "type",
                "accurate_tracking",
                "auto_cogs",
                "stock_management",
                "barcode",
                "barcode_type",
                "sku",
                "description",
                "thumbnail_id",
                "category_id",
                "category__name",
                "parent_id",
                "unit_group_id",
                "unit_group__name",
                "on_expiration",
                "expires",
                "searchable",
                "position",
                "pinned",
                "status",
                "user__username",
                "created_at",
            ],
        }
        result = commonQuery.fetchPaginatedData(Product, data, fieldConfig, options, request=request, tenant_config=True)
        product_ids = [item["id"] for item in result["items"]]
        unit_quantities_by_product = {}
        if product_ids:
            unit_quantities = commonQuery.findAllRecords(
                ProductUnitQuantity,
                {"product_id__in": product_ids},
                {
                    "attributes": [
                        "id",
                        "product_id",
                        "unit_id",
                        "unit__name",
                        "quantity",
                        "sale_price",
                    ],
                    "order": ["id"],
                },
                request=request,
                tenant_config=True,
            )
            for unit_quantity in unit_quantities:
                product_id = unit_quantity.get("product_id")
                if product_id not in unit_quantities_by_product:
                    unit_quantities_by_product[product_id] = unit_quantity
        for item in result["items"]:
            item["category_name"] = item.pop("category__name", None)
            item["tax_group_name"] = item.pop("tax_group__name", None)
            item["unit_group_name"] = item.pop("unit_group__name", None)
            item["user_username"] = item.pop("user__username", None)
            first_unit_quantity = unit_quantities_by_product.get(item["id"]) or {}
            item["unit_name"] = first_unit_quantity.get("unit__name")
            item["selling_price"] = first_unit_quantity.get("sale_price") or 0
            item["current_stock"] = first_unit_quantity.get("quantity") or 0
        return successResponse("Products retrieved successfully.", data=result)

    @staticmethod
    def getProducts(request):
        products = commonQuery.branchScopedQueryset(Product, {}, request)
        products = products.exclude(status=2).exclude(product_type="variation").order_by("position", "name").select_related("category", "tax_group", "unit_group", "parent").prefetch_related("unit_quantities", "gallery", "variations")
        return successResponse("Products retrieved successfully.", data=[ProductService.serializeProduct(product, request) for product in products])

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Product,
            {},
            {
                "attributes": [
                    "id",
                    "name",
                    "sku",
                    "barcode",
                    "product_type",
                    "type",
                    "stock_management",
                    "unit_group_id",
                ],
                "order": ["position", "name"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def searchProduct(data, request):
        search = (data or {}).get("search") or ""
        limit = int((data or {}).get("limit") or 5)
        queryset = (
            commonQuery.branchScopedQueryset(Product, {}, request)
            .exclude(status=2)
            .filter(Q(name__icontains=search) | Q(sku__icontains=search) | Q(barcode__icontains=search))
            .select_related("category", "tax_group", "unit_group", "parent")
            .prefetch_related("unit_quantities", "gallery", "variations")
            .order_by("name")[:limit]
        )
        return successResponse("Products retrieved successfully.", data=[ProductService.serializeProduct(product, request) for product in queryset])

    @staticmethod
    def getProductUsingArgument(identifier, request, argument="id"):
        filters = {"id": identifier}
        if argument == "sku":
            filters = {"sku": identifier}
        elif argument == "barcode":
            filters = {"barcode": identifier}
        elif argument != "id":
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unsupported product lookup argument.")
        product = (
            commonQuery.branchScopedQueryset(Product, filters, request)
            .exclude(status=2)
            .select_related("category", "tax_group", "unit_group", "parent")
            .prefetch_related("unit_quantities", "gallery", "variations")
            .first()
        )
        if product is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        return product

    @staticmethod
    def getByIdentifier(identifier, request, argument="id"):
        return successResponse("Product retrieved successfully.", data=ProductService.serializeProduct(ProductService.getProductUsingArgument(identifier, request, argument), request))

    @staticmethod
    def getVariations(request, identifier=None, argument="id"):
        if identifier is None:
            variations = commonQuery.branchScopedQueryset(Product, {"product_type": "variation"}, request).exclude(status=2).order_by("position", "name")
        else:
            product = ProductService.getProductUsingArgument(identifier, request, argument)
            variations = product.variations.exclude(status=2).order_by("position", "name")
        return successResponse("Product variations retrieved successfully.", data=[ProductService.serializeProduct(variation, request) for variation in variations])

    @staticmethod
    def getHistory(identifier, request, argument="id"):
        product = ProductService.getProductUsingArgument(identifier, request, argument)
        histories = commonQuery.findAllRecords(
            ProductHistory,
            {"product_id": product.id},
            {"include": [{"path": "unit", "fields": ["id", "name", "identifier"]}], "order": ["id"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Product history retrieved successfully.", data=histories)

    @staticmethod
    def resetProduct(identifier, request, argument="id"):
        product = ProductService.getProductUsingArgument(identifier, request, argument)
        products = list(product.variations.exclude(status=2)) if product.product_type == "variable" else [product]
        if product.product_type == "variable" and not products:
            return successResponse(f"Unable to reset this variable product \"{product.name}\", since it doesn't seems to have any variations", data=None)
        result = []
        for item in products:
            commonQuery.branchScopedQueryset(ProductHistory, {"product_id": item.id}, request).delete()
            commonQuery.branchScopedQueryset(ProductUnitQuantity, {"product_id": item.id}, request).delete()
            result.append({"product": ProductService.serializeProduct(item, request, include_relations=False)})
        message = "The product variations has been reset" if product.product_type == "variable" else "The product has been reset."
        return successResponse(message, data={"result": result} if product.product_type == "variable" else result[0])

    @staticmethod
    def reorderProducts(data, request):
        items = (data or {}).get("items") or []
        for index, item in enumerate(items):
            product_id = item.get("id") if isinstance(item, dict) else item
            commonQuery.branchScopedQueryset(Product, {"id": product_id}, request).exclude(status=2).update(position=index)
        return successResponse("Products have been successfully reordered.")

    @staticmethod
    def getProcuredProducts(product_id, request):
        from apps.purchases.models import ProcurementsProduct

        ProductUnitQuantityService.ensureProduct(product_id, request)
        rows = commonQuery.findAllRecords(
            ProcurementsProduct,
            {"product_id": product_id},
            {
                "attributes": [
                    "id",
                    "name",
                    "procurement_id",
                    "procurement__name",
                    "product_id",
                    "purchase_price",
                    "quantity",
                    "available_quantity",
                    "barcode",
                    "expiration_date",
                    "unit_id",
                    "unit__name",
                    "created_at",
                ],
                "order": ["-id"],
            },
            request=request,
            tenant_config=True,
        )
        for row in rows:
            row["procurement"] = {"name": row.pop("procurement__name", None)}
            row["unit_name"] = row.pop("unit__name", None)
        return successResponse("Procured products retrieved successfully.", data=rows)

    @staticmethod
    def convertUnitQuantities(product_id, data, request):
        product = ProductService.getProductUsingArgument(product_id, request)
        if product.stock_management != Product.STOCK_MANAGEMENT[0][0]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "You cannot convert unit on a product having stock management disabled.")
        from_unit = commonQuery.branchScopedQueryset(Unit, {"id": data.get("from")}, request).exclude(status=2).first()
        to_unit = commonQuery.branchScopedQueryset(Unit, {"id": data.get("to")}, request).exclude(status=2).first()
        if from_unit is None or to_unit is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unit not found.")
        quantity = decimalValue(data.get("quantity"))
        if quantity == 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "The quantity to convert can't be zero.")
        if from_unit.id == to_unit.id:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "The source and the destination unit can't be the same.")
        if from_unit.group_id != to_unit.group_id:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "The source unit and the destination unit doesn't belong to the same unit group.")
        source = ProductStockService.resolveUnitQuantity(product.id, from_unit.id, request)
        destination = commonQuery.branchScopedQueryset(ProductUnitQuantity, {"product_id": product.id, "unit_id": to_unit.id}, request).exclude(status=2).first()
        if destination is None:
            destination = commonQuery.createInstance(
                ProductUnitQuantity,
                {"product_id": product.id, "unit_id": to_unit.id, "quantity": 0, "visible": False},
                request=request,
                tenant_config=True,
            )
        if decimalValue(source.quantity) < quantity:
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"The source unit \"({from_unit.name})\" for the product \"{product.name}\", does not have enough quantity.")
        if from_unit.value < to_unit.value:
            total_possible_slots = int((decimalValue(from_unit.value) * quantity) // decimalValue(to_unit.value))
            quantity = decimalValue(total_possible_slots) * decimalValue(to_unit.value)
        final_destination_quantity = (decimalValue(from_unit.value) * quantity) / decimalValue(to_unit.value)
        if final_destination_quantity < 1:
            raise api_error(400, ErrorCodes.BAD_REQUEST, f"The conversion from \"{from_unit.name}\" will cause a decimal value less than one count of the destination unit \"{to_unit.name}\".")
        with transaction.atomic():
            ProductStockService.recordStockHistory(
                ProductHistory.ACTION_CONVERT_OUT,
                {"product_id": product.id, "unit_id": from_unit.id, "quantity": quantity, "unit_price": source.cogs or 0, "total_price": decimalValue(source.cogs or 0) * quantity, "procurement_product_id": data.get("procurement_product_id")},
                request,
            )
            unit_price = (decimalValue(source.cogs or 0) / final_destination_quantity) if final_destination_quantity else 0
            ProductStockService.recordStockHistory(
                ProductHistory.ACTION_CONVERT_IN,
                {"product_id": product.id, "unit_id": to_unit.id, "quantity": final_destination_quantity, "unit_price": unit_price, "total_price": decimalValue(source.cogs or 0) * quantity, "procurement_product_id": data.get("procurement_product_id")},
                request,
            )
        return successResponse(f"The conversion of {quantity}({from_unit.name}) to {final_destination_quantity}({to_unit.name}) was successful")

    @staticmethod
    def searchUsingBarcode(reference, request):
        if not reference:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Barcode is required.")
        
        from apps.common.commonQuery import safeAuthContext
        ctx = safeAuthContext(request)
        company = ctx.get("company_id")
        branch = ctx.get("branch_id")

        if ProductService.isScaleBarcode(reference, company, branch):
            parsed = ProductService.parseScaleBarcode(reference, company, branch)
            product_code = parsed["product_code"]
            scale_value = parsed["value"]
            unit_quantity = commonQuery.findOneRecord(
                ProductUnitQuantity,
                {"scale_plu": product_code},
                options={"include": [{"path": "product", "fields": ["id", "name", "sku", "barcode", "product_type", "unit_group_id", "status"]}, {"path": "unit", "fields": ["id", "name", "identifier"]}]},
                request=request,
                tenant_config=True,
            )
            if unit_quantity is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, f"Product with scale PLU '{product_code}' not found.")
            data = ProductService.attachDisplayData(dict(unit_quantity.get("product") or {}), request)
            data["matched_unit_quantity"] = dict(unit_quantity)
            data["scale_value"] = scale_value
            return successResponse("Product retrieved successfully.", data=data)

        product = commonQuery.findOneRecord(Product, {"barcode": reference}, request=request, tenant_config=True)
        if product:
            data = ProductService.attachDisplayData(dict(product), request)
            data["matched_unit_quantity"] = None
            return successResponse("Product retrieved successfully.", data=data)
        unit_quantity = commonQuery.findOneRecord(
            ProductUnitQuantity,
            {"barcode": reference},
            options={"include": [{"path": "product", "fields": ["id", "name", "sku", "barcode", "product_type", "unit_group_id", "status"]}, {"path": "unit", "fields": ["id", "name", "identifier"]}]},
            request=request,
            tenant_config=True,
        ) or commonQuery.findOneRecord(
            ProductUnitQuantity,
            {"scale_plu": reference},
            options={"include": [{"path": "product", "fields": ["id", "name", "sku", "barcode", "product_type", "unit_group_id", "status"]}, {"path": "unit", "fields": ["id", "name", "identifier"]}]},
            request=request,
            tenant_config=True,
        )
        if unit_quantity is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        data = ProductService.attachDisplayData(dict(unit_quantity.get("product") or {}), request)
        data["matched_unit_quantity"] = dict(unit_quantity)
        return successResponse("Product retrieved successfully.", data=data)

    @staticmethod
    def delete(data, request):
        ids = data.get("ids")
        if not isinstance(ids, list):
            ids = [ids]
        products = list(
            commonQuery.branchScopedQueryset(Product, {"id__in": ids}, request)
            .exclude(status=2)
            .values("id", "category_id")
        )
        affected_category_ids = list({product["category_id"] for product in products if product.get("category_id")})
        for product in products:
            commonQuery.branchScopedQueryset(ProductSubItem, {"parent_id": product["id"]}, request).delete()
            commonQuery.branchScopedQueryset(ProductSubItem, {"product_id": product["id"]}, request).delete()
            commonQuery.branchScopedQueryset(ProductGallery, {"product_id": product["id"]}, request).delete()
            commonQuery.branchScopedQueryset(ProductTax, {"product_id": product["id"]}, request).delete()
            commonQuery.branchScopedQueryset(ProductUnitQuantity, {"product_id": product["id"]}, request).delete()
            commonQuery.branchScopedQueryset(ProductHistoryCombined, {"product_id": product["id"]}, request).delete()
            commonQuery.branchScopedQueryset(ProductHistory, {"product_id": product["id"]}, request).delete()
        count = commonQuery.softDeleteById(Product, ids, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        for category_id in affected_category_ids:
            CategoryService.computeProducts(category_id, request)
        return successResponse("Products deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(Product, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        return successResponse("Product status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getById(product_id, request):
        product = commonQuery.findOneRecord(Product, product_id, request=request, tenant_config=True)
        if product is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        data = ProductService.attachDisplayData(dict(product), request)
        data["gallery"] = commonQuery.findAllRecords(
            ProductGallery,
            {"product_id": product_id},
            {"attributes": ["id", "name", "media_id", "url", "order", "featured", "status"], "order": ["order", "id"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Product retrieved successfully.", data=data)

    @staticmethod
    def isScaleBarcodeEnabled(company, branch):
        from apps.settings.services import OptionSettingService
        val = OptionSettingService.getOptionValue(company, branch, "scale_barcode_enabled", "no")
        return val in [True, "yes"]

    @staticmethod
    def isScaleBarcode(barcode, company, branch):
        if not ProductService.isScaleBarcodeEnabled(company, branch):
            return False
        from apps.settings.services import OptionSettingService
        prefix = str(OptionSettingService.getOptionValue(company, branch, "scale_barcode_prefix", "2"))
        if not str(barcode).startswith(prefix):
            return False
        product_length = int(OptionSettingService.getOptionValue(company, branch, "scale_barcode_product_length", 5))
        value_length = int(OptionSettingService.getOptionValue(company, branch, "scale_barcode_value_length", 5))
        expected_length = len(prefix) + product_length + value_length + 1
        if len(str(barcode)) != expected_length:
            return False
        return str(barcode).isdigit()

    @staticmethod
    def parseScaleBarcode(barcode, company, branch):
        if not ProductService.isScaleBarcode(barcode, company, branch):
            raise Exception("Invalid scale barcode format")
        from apps.settings.services import OptionSettingService
        prefix = str(OptionSettingService.getOptionValue(company, branch, "scale_barcode_prefix", "2"))
        product_length = int(OptionSettingService.getOptionValue(company, branch, "scale_barcode_product_length", 5))
        value_length = int(OptionSettingService.getOptionValue(company, branch, "scale_barcode_value_length", 5))
        barcode_type = OptionSettingService.getOptionValue(company, branch, "scale_barcode_type", "weight")
        
        prefix_len = len(prefix)
        product_code = str(barcode)[prefix_len : prefix_len + product_length]
        raw_value = str(barcode)[prefix_len + product_length : prefix_len + product_length + value_length]
        
        try:
            val_float = float(raw_value)
        except ValueError:
            val_float = 0.0

        if barcode_type == "weight":
            value = val_float / 1000.0  # grams to kg
        else:
            value = val_float / 100.0   # cents to main currency
            
        return {
            "product_code": product_code,
            "value": value,
            "type": barcode_type,
            "original_barcode": barcode,
        }

    @staticmethod
    def generateScalePLU(product_id, unit_quantity_id, request):
        product = commonQuery.findOneInstance(
            Product,
            product_id,
            options={"select_related": ["category", "category__scale_range"]},
            request=request,
            tenant_config=True,
        )
        if not product:
            raise Exception("Product not found.")
        if not product.category:
            raise Exception("Product must have a category to generate PLU code.")
        if not product.category.scale_range:
            raise Exception(f"Category '{product.category.name}' does not have a PLU range assigned.")
            
        scale_range = product.category.scale_range
        plu = scale_range.getNextPLU()
        
        # Check if unique
        from apps.catalog.models import ProductUnitQuantity
        existing = commonQuery.branchScopedQueryset(
            ProductUnitQuantity,
            {"scale_plu": plu},
            request=request,
        ).exclude(id=unit_quantity_id).first()
        
        if existing:
            scale_range.incrementNextPLU()
            return ProductService.generateScalePLU(product_id, unit_quantity_id, request)
            
        scale_range.incrementNextPLU()
        return plu

    @staticmethod
    def validateAndFormatPLU(plu, company, branch, product_length=None):
        if product_length is None:
            from apps.settings.services import OptionSettingService
            product_length = int(OptionSettingService.getOptionValue(company, branch, "scale_barcode_product_length", 5))
            
        import re
        plu_clean = re.sub(r"[^0-9]", "", str(plu))
        if not plu_clean:
            raise Exception("PLU code cannot be empty.")
            
        plu_padded = plu_clean.zfill(product_length)
        if len(plu_padded) > product_length:
            raise Exception(f"PLU code is too long. Maximum length is {product_length} digits.")
        return plu_padded

    @staticmethod
    def isPLUUnique(plu, exclude_unit_quantity_id=None, request=None):
        from apps.catalog.models import ProductUnitQuantity
        qs = commonQuery.branchScopedQueryset(ProductUnitQuantity, {"scale_plu": plu}, request=request)
        if exclude_unit_quantity_id:
            qs = qs.exclude(id=exclude_unit_quantity_id)
        return not qs.exists()

    @staticmethod
    def addGalleryImage(product_id, image, request):
        product = commonQuery.findOneRecord(Product, product_id, request=request, tenant_config=True)
        if product is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        
        image_url = saveProductImage(image, request)
        if not image_url:
            raise api_error(400, ErrorCodes.INVALID_DATA, "Failed to save image file.")
            
        gallery_entry = commonQuery.createRecord(
            ProductGallery,
            {"product_id": product_id, "url": image_url, "featured": False},
            request=request,
            tenant_config=True,
        )
        return successResponse("Gallery image uploaded successfully.", data=dict(gallery_entry))

    @staticmethod
    def deleteGalleryImage(product_id, gallery_id, request):
        gallery = commonQuery.findOneRecord(ProductGallery, gallery_id, request=request, tenant_config=True)
        if gallery is None or gallery["product_id"] != product_id:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Gallery image not found.")
        
        commonQuery.deleteRecord(ProductGallery, gallery_id, request=request, tenant_config=True)
        return successResponse("Gallery image deleted successfully.")



class ProductStockService:
    @staticmethod
    def requestFromJob(job):
        from apps.common.helpers import requestFromJobUser

        return requestFromJobUser(job)

    STOCK_REDUCE_ACTIONS = {
        ProductHistory.ACTION_TRANSFER_OUT,
        ProductHistory.ACTION_REMOVED,
        ProductHistory.ACTION_SOLD,
        ProductHistory.ACTION_DEFECTIVE,
        ProductHistory.ACTION_LOST,
        ProductHistory.ACTION_ADJUSTMENT_SALE,
        ProductHistory.ACTION_DELETED,
        ProductHistory.ACTION_CONVERT_OUT,
    }
    STOCK_INCREASE_ACTIONS = {
        ProductHistory.ACTION_ADDED,
        ProductHistory.ACTION_RETURNED,
        ProductHistory.ACTION_TRANSFER_IN,
        ProductHistory.ACTION_STOCKED,
        ProductHistory.ACTION_VOID_RETURN,
        ProductHistory.ACTION_TRANSFER_REJECTED,
        ProductHistory.ACTION_TRANSFER_CANCELED,
        ProductHistory.ACTION_ADJUSTMENT_RETURN,
        ProductHistory.ACTION_CONVERT_IN,
    }
    MANUAL_ACTIONS = {
        ProductHistory.ACTION_ADDED,
        ProductHistory.ACTION_DELETED,
        ProductHistory.ACTION_DEFECTIVE,
        ProductHistory.ACTION_LOST,
        ProductHistory.ACTION_SET,
    }
    COMBINED_PROCURED_ACTIONS = {
        ProductHistory.ACTION_ADDED,
        ProductHistory.ACTION_STOCKED,
        ProductHistory.ACTION_ADJUSTMENT_RETURN,
        ProductHistory.ACTION_CONVERT_IN,
        ProductHistory.ACTION_RETURNED,
        ProductHistory.ACTION_TRANSFER_IN,
        ProductHistory.ACTION_TRANSFER_CANCELED,
        ProductHistory.ACTION_TRANSFER_REJECTED,
    }
    COMBINED_DEFECTIVE_ACTIONS = {
        ProductHistory.ACTION_DELETED,
        ProductHistory.ACTION_LOST,
        ProductHistory.ACTION_REMOVED,
        ProductHistory.ACTION_DEFECTIVE,
    }

    @staticmethod
    def stockEnabled(product):
        return product.get("stock_management") != "disabled" and product.get("type") == "materialized"

    @staticmethod
    def resolveUnitQuantity(product_id, unit_id, request, required=True):
        if not unit_id:
            if required:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Unit is required for stock movement.")
            return None
        unit_quantity = commonQuery.branchScopedQueryset(
            ProductUnitQuantity,
            {"product_id": product_id, "unit_id": unit_id, "status__in": [0, 1]},
            request,
        ).select_for_update().first()
        if unit_quantity is None and required:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product unit quantity not found.")
        return unit_quantity

    @staticmethod
    def recordStockHistory(action, data, request):
        product = commonQuery.findOneRecord(
            Product,
            data.get("product_id"),
            request=request,
            tenant_config=True,
        )
        if product is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
        if not ProductStockService.stockEnabled(product):
            return None

        quantity = decimalValue(data.get("quantity"))
        if quantity <= 0 and action != ProductHistory.ACTION_SET:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Quantity must be greater than 0.")

        unit_id = data.get("unit_id")
        unit_quantity = ProductStockService.resolveUnitQuantity(product["id"], unit_id, request)
        before_quantity = decimalValue(unit_quantity.quantity)
        history_action = action

        if action == ProductHistory.ACTION_SET:
            after_quantity = quantity
            quantity_delta = after_quantity - before_quantity
            history_quantity = abs(quantity_delta)
            if quantity_delta > 0:
                history_action = ProductHistory.ACTION_ADDED
            elif quantity_delta < 0:
                history_action = ProductHistory.ACTION_REMOVED
            else:
                history_quantity = 0
        elif action in ProductStockService.STOCK_INCREASE_ACTIONS:
            history_quantity = quantity
            after_quantity = before_quantity + quantity
        elif action in ProductStockService.STOCK_REDUCE_ACTIONS:
            history_quantity = quantity
            after_quantity = before_quantity - quantity
            if after_quantity < 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, f"Insufficient stock for {product.get('name')}.")
        else:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unsupported stock movement action.")

        unit_price = decimalValue(data.get("unit_price"))
        total_price = decimalValue(data.get("total_price"))
        if not total_price and history_quantity:
            total_price = history_quantity * unit_price

        unit_quantity.quantity = float(after_quantity)
        if data.get("cogs") is not None:
            unit_quantity.cogs = float(decimalValue(data.get("cogs")))
        unit_quantity.save(update_fields=["quantity", "cogs", "updated_at"] if data.get("cogs") is not None else ["quantity", "updated_at"])

        history = commonQuery.createRecord(
            ProductHistory,
            {
                "product_id": product["id"],
                "procurement_id": data.get("procurement_id"),
                "procurement_product_id": data.get("procurement_product_id"),
                "order_id": data.get("order_id"),
                "order_product_id": data.get("order_product_id"),
                "operation_type": history_action,
                "unit_id": unit_quantity.unit_id,
                "before_quantity": before_quantity,
                "quantity": history_quantity,
                "after_quantity": after_quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "description": data.get("description") or "",
            },
            request=request,
            tenant_config=True,
        )
        ProductStockService.computeCogsIfNecessary(history, request)
        ProductStockService.combineProductHistory(history, product, request)
        return history

    @staticmethod
    def computeCogsIfNecessary(history, request):
        if not history:
            return None
        product = commonQuery.findOneRecord(
            Product,
            history.get("product_id"),
            request=request,
            tenant_config=True,
        )
        if not product or not product.get("auto_cogs"):
            return None
        unit_id = history.get("unit_id")
        if not unit_id:
            return None
        totals = commonQuery.branchScopedQueryset(
            ProductHistory,
            {
                "product_id": product["id"],
                "unit_id": unit_id,
                "operation_type__in": [ProductHistory.ACTION_CONVERT_IN, ProductHistory.ACTION_STOCKED],
                "status__in": [0, 1],
            },
            request,
        ).aggregate(total_quantity=Sum("quantity"), total_price=Sum("total_price"))
        total_quantity = decimalValue(totals.get("total_quantity") or 0)
        total_price = decimalValue(totals.get("total_price") or 0)
        if total_quantity <= 0 or total_price <= 0:
            return None
        cogs = total_price / total_quantity
        commonQuery.branchScopedQueryset(
            ProductUnitQuantity,
            {"product_id": product["id"], "unit_id": unit_id},
            request,
        ).exclude(status=2).update(cogs=float(cogs), updated_at=timezone.now())
        return cogs

    @staticmethod
    def handleStockHistoryJob(history_id, request):
        history = commonQuery.findOneRecord(
            ProductHistory,
            history_id,
            request=request,
            tenant_config=True,
        )
        if history is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product history not found.")
        cogs = ProductStockService.computeCogsIfNecessary(history, request)
        from apps.reports.services import ReportService

        history_created_at = history.get("created_at")
        report_date = (
            timezone.localtime(history_created_at).date()
            if hasattr(history_created_at, "date") and timezone.is_aware(history_created_at)
            else history_created_at.date()
            if hasattr(history_created_at, "date")
            else timezone.localdate()
        )
        ReportService.recomputeStockCombined({"date": report_date.isoformat()}, request)
        return successResponse("Product history processed successfully.", data={"history_id": history_id, "cogs": cogs, "date": report_date})

    @staticmethod
    def jobHandlers():
        return {
            "process_product_history": lambda data, job: ProductStockService.handleStockHistoryJob(
                data.get("history_id") or data.get("product_history_id"),
                ProductStockService.requestFromJob(job),
            ),
        }

    @staticmethod
    def combineProductHistory(history, product, request):
        if not history:
            return None

        history_created_at = history.get("created_at")
        if hasattr(history_created_at, "date"):
            history_date = (
                timezone.localtime(history_created_at).date()
                if timezone.is_aware(history_created_at)
                else history_created_at.date()
            )
        else:
            history_date = timezone.localdate()

        combined_filters = commonQuery.enrichTenantData(
            ProductHistoryCombined,
            {
                "product_id": history.get("product_id"),
                "unit_id": history.get("unit_id"),
                "date": history_date,
            },
            request,
            tenant_config=True,
        )
        combined, created = commonQuery.getOrCreateRecord(
            ProductHistoryCombined,
            combined_filters,
            defaults={
                "user_id": request.user.id,
                "name": product.get("name") or "",
                "initial_quantity": history.get("before_quantity") or 0,
                "procured_quantity": 0,
                "sold_quantity": 0,
                "defective_quantity": 0,
                "final_quantity": 0,
            },
            tenant_config={},
            return_plain=False,
        )
        if not created and not combined.name:
            combined.name = product.get("name") or combined.name

        quantity = float(decimalValue(history.get("quantity")))
        operation_type = history.get("operation_type")
        if operation_type in ProductStockService.COMBINED_PROCURED_ACTIONS:
            combined.procured_quantity = float(combined.procured_quantity or 0) + quantity
        elif operation_type == ProductHistory.ACTION_SOLD:
            combined.sold_quantity = float(combined.sold_quantity or 0) + quantity
        elif operation_type in ProductStockService.COMBINED_DEFECTIVE_ACTIONS:
            combined.defective_quantity = float(combined.defective_quantity or 0) + quantity

        combined.final_quantity = (
            float(combined.initial_quantity or 0)
            + float(combined.procured_quantity or 0)
            - float(combined.sold_quantity or 0)
            - float(combined.defective_quantity or 0)
        )
        combined.save(
            update_fields=[
                "name",
                "procured_quantity",
                "sold_quantity",
                "defective_quantity",
                "final_quantity",
                "updated_at",
            ]
        )
        return combined

    @staticmethod
    def applyManualAdjustment(data, request):
        products = data.get("products") or []
        if not products:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "At least one product is required.")
        histories = []
        with transaction.atomic():
            for item in products:
                action = item.get("adjust_action")
                if action not in ProductStockService.MANUAL_ACTIONS:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Unsupported stock adjustment action.")
                adjust_unit = item.get("adjust_unit") or {}
                histories.append(
                    ProductStockService.recordStockHistory(
                        action,
                        {
                            "product_id": item.get("id"),
                            "procurement_product_id": item.get("procurement_product_id"),
                            "unit_id": adjust_unit.get("unit_id"),
                            "quantity": item.get("adjust_quantity"),
                            "unit_price": adjust_unit.get("sale_price") or 0,
                            "description": item.get("adjust_reason") or "",
                        },
                        request,
                    )
                )
        return successResponse("Stock adjustment completed successfully.", data=histories)


class ProductUnitQuantityService:
    @staticmethod
    def attachDisplayData(data):
        unit = data.get("unit") or {}
        convert_unit = data.get("convert_unit") or {}
        data["unit_name"] = unit.get("name") if unit else None
        data["unit_identifier"] = unit.get("identifier") if unit else None
        data["convert_unit_name"] = convert_unit.get("name") if convert_unit else None
        data["convert_unit_identifier"] = convert_unit.get("identifier") if convert_unit else None
        return data

    @staticmethod
    def ensureProduct(product_id, request):
        product_id = validateTenantRelationId(Product, product_id, request=request, label="Product", tenant_config=True)
        return {"id": product_id}

    @staticmethod
    def ensureUnit(unit_id, request, label="Unit"):
        unit_id = validateTenantRelationId(Unit, unit_id, request=request, label=label, tenant_config=True)
        return {"id": unit_id}

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
            messages={"barcode": "Barcode already exists on another product unit."},
        )

    @staticmethod
    def getAll(product_id, request):
        ProductUnitQuantityService.ensureProduct(product_id, request)
        rows = commonQuery.findAllRecords(
            ProductUnitQuantity,
            {"product_id": product_id},
            {
                "include": [
                    {"path": "unit", "fields": ["id", "name", "identifier"]},
                    {"path": "convert_unit", "fields": ["id", "name", "identifier"]},
                ],
                "order": ["id"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Product unit quantities retrieved successfully.", data=[ProductUnitQuantityService.attachDisplayData(dict(row)) for row in rows])

    @staticmethod
    def getByProductAndUnit(product_id, unit_id, request):
        ProductUnitQuantityService.ensureProduct(product_id, request)
        row = commonQuery.findOneRecord(
            ProductUnitQuantity,
            {"product_id": product_id, "unit_id": unit_id},
            options={
                "include": [
                    {"path": "unit", "fields": ["id", "name", "identifier"]},
                    {"path": "convert_unit", "fields": ["id", "name", "identifier"]},
                ]
            },
            request=request,
            tenant_config=True,
        )
        if row is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "No stock is provided for the requested product.")
        return successResponse("Product unit quantity retrieved successfully.", data=ProductUnitQuantityService.attachDisplayData(dict(row)))

    @staticmethod
    def create(product_id, data, request):
        with transaction.atomic():
            product = ProductUnitQuantityService.ensureProduct(product_id, request)
            unit = ProductUnitQuantityService.ensureUnit(data["unit_id"], request)
            if data.get("convert_unit_id"):
                data["convert_unit_id"] = ProductUnitQuantityService.ensureUnit(data["convert_unit_id"], request, "Convert unit")["id"]
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
            if data.get("scale_plu"):
                validateUniqueFields(
                    ProductUnitQuantity,
                    {"scale_plu": data.get("scale_plu")},
                    request=request,
                    scope="branch",
                    status_in=(0, 1),
                    messages={"scale_plu": "Scale PLU already exists."},
                )
            unit_quantity = commonQuery.createRecord(ProductUnitQuantity, {**data, "product_id": product["id"], "unit_id": unit["id"]}, request=request, tenant_config=True)
            return successResponse("Product unit quantity created successfully.", data=unit_quantity)

    @staticmethod
    def update(product_id, unit_quantity_id, data, request):
        with transaction.atomic():
            product = ProductUnitQuantityService.ensureProduct(product_id, request)
            unit_quantity = commonQuery.findOneRecord(ProductUnitQuantity, {"id": unit_quantity_id, "product_id": product["id"]}, request=request, tenant_config=True)
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
                data["convert_unit_id"] = ProductUnitQuantityService.ensureUnit(data["convert_unit_id"], request, "Convert unit")["id"]
            elif "convert_unit_id" in data:
                data["convert_unit_id"] = None
            ProductUnitQuantityService.ensureBarcodeAvailable(data.get("barcode"), request, unit_quantity_id)
            if data.get("scale_plu"):
                validateUniqueFields(
                    ProductUnitQuantity,
                    {"scale_plu": data.get("scale_plu")},
                    request=request,
                    scope="branch",
                    exclude_id=unit_quantity_id,
                    status_in=(0, 1),
                    messages={"scale_plu": "Scale PLU already exists."},
                )
            updated = commonQuery.updateRecordById(ProductUnitQuantity, {"id": unit_quantity_id, "product_id": product["id"]}, data, request=request, tenant_config=True)
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product unit quantity not found.")
            return successResponse("Product unit quantity updated successfully.", data=updated)

    @staticmethod
    def delete(product_id, unit_quantity_id, request):
        ProductUnitQuantityService.ensureProduct(product_id, request)
        count = commonQuery.softDeleteById(ProductUnitQuantity, {"id": unit_quantity_id, "product_id": product_id}, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Product unit quantity not found.")
        return successResponse("Product unit quantity deleted successfully.")
