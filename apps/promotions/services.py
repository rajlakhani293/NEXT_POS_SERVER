# type: ignore
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Category, Product
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildUniqueValue, decimalValue as money, validateTenantRelationIds, validateUniqueFields
from apps.common.responses import successResponse
from apps.customers.models import Customer, CustomerCoupon, CustomerGroup
from apps.promotions.models import (
    OrdersCoupon,
    Coupon,
    CouponCategory,
    CouponCustomer,
    CouponCustomerGroup,
    CouponProduct,
)

LINK_FIELDS = ["product_ids", "category_ids", "customer_ids", "customer_group_ids"]


def buildCouponCode(code, request, exclude_id=None):
    base = slugify((code or "").strip() or "coupon").upper()
    if code:
        validateUniqueFields(
            Coupon,
            {"code": base},
            request=request,
            scope="branch",
            exclude_id=exclude_id,
            status_in=(0, 1),
            case_insensitive=["code"],
            messages={"code": "Coupon code already exists."},
        )
        return base
    return buildUniqueValue(Coupon, request, "code", base, exclude_id=exclude_id)


def splitCouponData(data):
    coupon_data = dict(data or {})
    links = {}
    for field in LINK_FIELDS:
        if field in coupon_data:
            links[field] = coupon_data.pop(field) or []
    for nullable_field in ["valid_until", "valid_hours_start", "valid_hours_end"]:
        if coupon_data.get(nullable_field) == "":
            coupon_data[nullable_field] = None
    return coupon_data, links


def validateIds(model, ids, request, label):
    return validateTenantRelationIds(model, ids or [], request=request, label=label)


def getExistingCouponTargetLinks(coupon_id, request):
    return {
        "product_ids": [
            item["product_id"]
            for item in commonQuery.findAllRecords(
                CouponProduct,
                {"coupon_id": coupon_id},
                {"attributes": ["product_id"]},
                request=request,
                tenant_config=True,
            )
        ],
        "category_ids": [
            item["category_id"]
            for item in commonQuery.findAllRecords(
                CouponCategory,
                {"coupon_id": coupon_id},
                {"attributes": ["category_id"]},
                request=request,
                tenant_config=True,
            )
        ],
        "customer_ids": [
            item["customer_id"]
            for item in commonQuery.findAllRecords(
                CouponCustomer,
                {"coupon_id": coupon_id},
                {"attributes": ["customer_id"]},
                request=request,
                tenant_config=True,
            )
        ],
        "customer_group_ids": [
            item["customer_group_id"]
            for item in commonQuery.findAllRecords(
                CouponCustomerGroup,
                {"coupon_id": coupon_id},
                {"attributes": ["customer_group_id"]},
                request=request,
                tenant_config=True,
            )
        ],
    }


def validateCouponTargetScope(links):
    has_target = any(links.get(field) for field in LINK_FIELDS)
    if not has_target:
        raise api_error(
            400,
            ErrorCodes.BAD_REQUEST,
            "Select at least one coupon target: product, category, customer, or customer group.",
        )


def validateCouponValueRange(coupon_data):
    minimum = money(coupon_data.get("minimum_cart_value") or 0)
    maximum = money(coupon_data.get("maximum_cart_value") or 0)
    if maximum > 0 and maximum < minimum:
        raise api_error(400, ErrorCodes.BAD_REQUEST, "Maximum cart value must be greater than minimum cart value.")


def replaceLinks(coupon_id, links, request):
    link_config = [
        (CouponProduct, Product, "product_ids", "product_id", "Product"),
        (CouponCategory, Category, "category_ids", "category_id", "Category"),
        (CouponCustomer, Customer, "customer_ids", "customer_id", "Customer"),
        (CouponCustomerGroup, CustomerGroup, "customer_group_ids", "customer_group_id", "Customer group"),
    ]

    for link_model, target_model, input_key, fk_key, label in link_config:
        if input_key not in links:
            continue
        ids = list(dict.fromkeys(links.get(input_key) or []))
        validateIds(target_model, ids, request, label)
        commonQuery.hardDeleteRecords(
            link_model,
            {"coupon_id": coupon_id},
            request=request,
            tenant_config=True,
        )
        for item_id in ids:
            commonQuery.createRecord(
                link_model,
                {"coupon_id": coupon_id, fk_key: item_id},
                request=request,
                tenant_config=True,
            )


def attachCouponTargets(coupon, request):
    data = dict(coupon)
    data.update(getExistingCouponTargetLinks(data["id"], request))
    data["target_summary"] = "All Customers"
    if data["customer_group_ids"] and data["customer_ids"]:
        data["target_summary"] = "Customer Groups + Particular Customers"
    elif data["customer_group_ids"]:
        data["target_summary"] = "Customer Groups"
    elif data["customer_ids"]:
        data["target_summary"] = "Particular Customers"
    return data


def attachCouponTargetsBatch(coupons, request):
    coupon_ids = [item["id"] for item in coupons]
    if not coupon_ids:
        return coupons

    link_config = [
        (CouponProduct, "product_ids", "product_id"),
        (CouponCategory, "category_ids", "category_id"),
        (CouponCustomer, "customer_ids", "customer_id"),
        (CouponCustomerGroup, "customer_group_ids", "customer_group_id"),
    ]
    links_by_coupon = {
        coupon_id: {field: [] for field in LINK_FIELDS}
        for coupon_id in coupon_ids
    }
    for link_model, output_field, relation_field in link_config:
        records = commonQuery.findAllRecords(
            link_model,
            {"coupon_id__in": coupon_ids},
            {"attributes": ["coupon_id", relation_field]},
            request=request,
            tenant_config=True,
        )
        for record in records:
            links_by_coupon[record["coupon_id"]][output_field].append(
                record[relation_field]
            )

    enriched = []
    for coupon in coupons:
        data = dict(coupon)
        data.update(links_by_coupon[data["id"]])
        data["target_summary"] = "All Customers"
        if data["customer_group_ids"] and data["customer_ids"]:
            data["target_summary"] = "Customer Groups + Particular Customers"
        elif data["customer_group_ids"]:
            data["target_summary"] = "Customer Groups"
        elif data["customer_ids"]:
            data["target_summary"] = "Particular Customers"
        enriched.append(data)
    return enriched


class CouponService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            coupon_data, links = splitCouponData(data)
            validateCouponTargetScope(links)
            validateCouponValueRange(coupon_data)
            coupon_data["code"] = buildCouponCode(coupon_data.get("code"), request)
            coupon = commonQuery.createRecord(
                Coupon,
                coupon_data,
                request=request,
                tenant_config=True,
            )
            replaceLinks(coupon["id"], links, request)
            return successResponse(
                "Coupon created successfully.",
                data=attachCouponTargets(coupon, request),
            )

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True], ["code", True, True], ["type", True, True]]
        options = {
            "attributes": [
                "id",
                "name",
                "code",
                "type",
                "discount_value",
                "minimum_cart_value",
                "maximum_cart_value",
                "valid_until",
                "valid_hours_start",
                "valid_hours_end",
                "limit_usage",
                "status",
                "user__username",
                "created_at",
            ],
        }
        result = commonQuery.fetchPaginatedData(
            Coupon,
            data,
            fieldConfig,
            options,
            request=request,
            tenant_config=True,
        )
        result["items"] = attachCouponTargetsBatch(result["items"], request)
        for item in result.get("items", []):
            item["user_username"] = item.pop("user__username", None)
        return successResponse("Coupons retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            Coupon,
            {},
            {"attributes": ["id", "name", "code", "type", "discount_value"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getById(coupon_id, request):
        coupon = commonQuery.findOneRecord(
            Coupon,
            coupon_id,
            request=request,
            tenant_config=True,
        )
        if coupon is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Coupon not found.")
        return successResponse("Coupon retrieved successfully.", data=attachCouponTargets(coupon, request))

    @staticmethod
    def update(data, request, coupon_id):
        with transaction.atomic():
            coupon = commonQuery.findOneRecord(
                Coupon,
                coupon_id,
                request=request,
                tenant_config=True,
            )
            if coupon is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Coupon not found.")
            coupon_data, links = splitCouponData(data)
            final_links = getExistingCouponTargetLinks(coupon_id, request)
            final_links.update(links)
            validateCouponTargetScope(final_links)
            validateCouponValueRange({**coupon, **coupon_data})
            if "code" in coupon_data:
                coupon_data["code"] = buildCouponCode(coupon_data.get("code"), request, exclude_id=coupon_id)
            updated = commonQuery.updateRecordById(
                Coupon,
                coupon_id,
                coupon_data,
                request=request,
                tenant_config=True,
            )
            replaceLinks(coupon_id, links, request)
            return successResponse("Coupon updated successfully.", data=attachCouponTargets(updated, request))

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(
            Coupon,
            data.get("ids"),
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Coupon not found.")
        return successResponse("Coupons deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(
            Coupon,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Coupon not found.")
        return successResponse("Coupon status updated successfully.", data={"updated_count": count, "status": status})

    @staticmethod
    def getCustomerCoupons(customer_id, data, request):
        customer = commonQuery.findOneRecord(
            Customer,
            customer_id,
            request=request,
            tenant_config=True,
        )
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")

        result = commonQuery.fetchPaginatedData(
            CustomerCoupon,
            {
                **(data or {}),
                "filter": {
                    **((data or {}).get("filter") or {}),
                    "customer_id": customer_id,
                },
            },
            [["name", True, True], ["code", True, True], ["coupon__name", True, True], ["coupon__type", True, True]],
            {
                "attributes": [
                    "id",
                    "coupon_id",
                    "coupon__name",
                    "coupon__type",
                    "coupon__discount_value",
                    "customer_id",
                    "name",
                    "code",
                    "usage",
                    "limit_usage",
                    "user__username",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        for item in result.get("items", []):
            coupon_type = item.get("coupon__type") or ""
            coupon_value = item.get("coupon__discount_value")
            item["coupon_type"] = "Percentage" if coupon_type == "percentage_discount" else "Flat"
            item["coupon_discount_value"] = f"{coupon_value}%" if coupon_type == "percentage_discount" else coupon_value
            item["user_username"] = item.pop("user__username", None) or "N/A"
        return successResponse("Customer coupons retrieved successfully.", data=result)

    @staticmethod
    def getCustomerCouponHistory(customer_id, customer_coupon_id, data, request):
        customer = commonQuery.findOneRecord(
            Customer,
            customer_id,
            request=request,
            tenant_config=True,
        )
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")

        customer_coupon = commonQuery.findOneRecord(
            CustomerCoupon,
            {"id": customer_coupon_id, "customer_id": customer_id},
            request=request,
            tenant_config=True,
        )
        if customer_coupon is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer coupon not found.")

        result = commonQuery.fetchPaginatedData(
            OrdersCoupon,
            {
                **(data or {}),
                "filter": {
                    **((data or {}).get("filter") or {}),
                    "customer_coupon_id": customer_coupon_id,
                },
            },
            [["sale_order__code", True, True], ["code", True, True], ["type", True, True]],
            {
                "attributes": [
                    "id",
                    "sale_order_id",
                    "sale_order__code",
                    "coupon_id",
                    "customer_coupon_id",
                    "code",
                    "type",
                    "discount_value",
                    "discount_amount",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        result["customer_coupon"] = customer_coupon
        return successResponse("Customer coupon history retrieved successfully.", data=result)

    @staticmethod
    def getGeneratedCoupons(data, request):
        result = commonQuery.fetchPaginatedData(
            CustomerCoupon,
            data,
            [["name", True, True], ["code", True, True], ["customer__full_name", True, True], ["coupon__name", True, True]],
            {
                "attributes": [
                    "id",
                    "name",
                    "usage",
                    "limit_usage",
                    "code",
                    "coupon_id",
                    "coupon__name",
                    "coupon__type",
                    "coupon__discount_value",
                    "customer_id",
                    "customer__full_name",
                    "status",
                    "user__username",
                    "created_at",
                ],
            },
            request=request,
            tenant_config=True,
        )
        for item in result.get("items", []):
            item["user_username"] = item.pop("user__username", None)
        return successResponse("Customer coupons retrieved successfully.", data=result)

    @staticmethod
    def getGeneratedCouponById(customer_coupon_id, request):
        customer_coupon = commonQuery.findOneRecord(
            CustomerCoupon,
            customer_coupon_id,
            request=request,
            tenant_config=True,
        )
        if customer_coupon is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer coupon not found.")
        return successResponse("Customer coupon retrieved successfully.", data=customer_coupon)

    @staticmethod
    def updateGeneratedCoupon(data, request, customer_coupon_id):
        customer_coupon = commonQuery.findOneRecord(
            CustomerCoupon,
            customer_coupon_id,
            request=request,
            tenant_config=True,
        )
        if customer_coupon is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer coupon not found.")
        updated = commonQuery.updateRecordById(
            CustomerCoupon,
            customer_coupon_id,
            data,
            request=request,
            tenant_config=True,
        )
        return successResponse("Customer coupon updated successfully.", data=updated)
