# type: ignore
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Category, Product
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildUniqueValue, validateTenantRelationIds, validateUniqueFields
from apps.common.responses import successResponse
from apps.customers.models import Customer, CustomerGroup
from apps.promotions.models import (
    AppliedCoupon,
    Coupon,
    CouponCategory,
    CouponCustomer,
    CouponCustomerGroup,
    CustomerCoupon,
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


class CouponService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            coupon_data, links = splitCouponData(data)
            validateCouponTargetScope(links)
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
        result["items"] = [attachCouponTargets(item, request) for item in result["items"]]
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
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
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
            [["code", True, True], ["coupon__name", True, True]],
            {
                "attributes": [
                    "id",
                    "coupon_id",
                    "coupon__name",
                    "customer_id",
                    "code",
                    "issued_at",
                    "expires_at",
                    "usage_count",
                    "is_redeemed",
                    "redeemed_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
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
            AppliedCoupon,
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
