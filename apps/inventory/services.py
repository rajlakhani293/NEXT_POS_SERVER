# type: ignore
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from apps.catalog.models import Product
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode
from apps.common.responses import successResponse
from apps.inventory.models import StockAdjustment, StockLedger


def decimalValue(value):
    return Decimal(str(value or 0))


def ledgerWithProductName(item, request):
    data = dict(item)
    data["product_name"] = None
    if data.get("product_id"):
        product = commonQuery.findOneRecord(
            Product,
            data["product_id"],
            options={"attributes": ["name"]},
            request=request,
            tenant_config=True,
        )
        data["product_name"] = product["name"] if product else None
    return data


class StockAdjustmentService:
    @staticmethod
    def create(data, request):
        adjustment_type = data.get("adjustment_type")
        if adjustment_type not in ["increase", "decrease"]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Adjustment type must be increase or decrease.")

        adjustment_qty = decimalValue(data.get("quantity"))
        if adjustment_qty <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Quantity must be greater than 0.")

        with transaction.atomic():
            product = commonQuery.findOneRecord(
                Product,
                data.get("product_id"),
                request=request,
                tenant_config=True,
            )
            if product is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product not found.")
            if not product.get("track_stock"):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Stock tracking is disabled for this product.")

            current_stock = decimalValue(product.get("current_stock"))
            if adjustment_type == "decrease" and current_stock < adjustment_qty:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Insufficient stock for adjustment.")

            new_stock = current_stock + adjustment_qty if adjustment_type == "increase" else current_stock - adjustment_qty
            adjustment = commonQuery.createRecord(
                StockAdjustment,
                {
                    "adjustment_type": adjustment_type,
                    "code": buildCode(StockAdjustment, "Stock Adjustment", None, request),
                    "reason": data.get("reason"),
                    "note": data.get("note") or "",
                },
                request=request,
                tenant_config=True,
            )
            Product.objects.filter(id=product["id"]).update(
                current_stock=F("current_stock") + adjustment_qty
                if adjustment_type == "increase"
                else F("current_stock") - adjustment_qty
            )
            ledger = commonQuery.createRecord(
                StockLedger,
                {
                    "product_id": product["id"],
                    "entry_type": "adjustment_in" if adjustment_type == "increase" else "adjustment_out",
                    "quantity": adjustment_qty if adjustment_type == "increase" else adjustment_qty * Decimal("-1"),
                    "unit_cost": data.get("unit_cost") or product.get("purchase_price") or 0,
                    "balance_after": new_stock,
                    "reference_type": "stock_adjustment",
                    "reference_id": adjustment["id"],
                    "note": data.get("note") or data.get("reason") or "",
                },
                request=request,
                tenant_config=True,
            )
            adjustment["product_id"] = product["id"]
            adjustment["product_name"] = product["name"]
            adjustment["quantity"] = adjustment_qty
            adjustment["balance_after"] = new_stock
            adjustment["ledger"] = ledger
            return successResponse("Stock adjustment created successfully.", data=adjustment)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["code", True, True], ["adjustment_type", True, True], ["reason", True, True]]
        options = {
            "attributes": ["id", "code", "adjustment_type", "reason", "note", "status", "created_at"],
        }
        result = commonQuery.fetchPaginatedData(
            StockAdjustment,
            data,
            fieldConfig,
            options,
            request=request,
            tenant_config=True,
        )
        return successResponse("Stock adjustments retrieved successfully.", data=result)

    @staticmethod
    def getById(adjustment_id, request):
        adjustment = commonQuery.findOneRecord(
            StockAdjustment,
            adjustment_id,
            request=request,
            tenant_config=True,
        )
        if adjustment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Stock adjustment not found.")
        return successResponse("Stock adjustment retrieved successfully.", data=adjustment)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(
            StockAdjustment,
            data.get("ids"),
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Stock adjustment not found.")
        return successResponse("Stock adjustments deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            StockAdjustment,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Stock adjustment not found.")
        return successResponse("Stock adjustment status updated successfully.", data={"updated_count": count, "status": status})


class StockLedgerService:
    @staticmethod
    def getAll(data, request):
        fieldConfig = [["entry_type", True, True], ["reference_type", True, True], ["note", True, True]]
        options = {
            "attributes": [
                "id",
                "product_id",
                "entry_type",
                "quantity",
                "unit_cost",
                "balance_after",
                "reference_type",
                "reference_id",
                "note",
                "created_at",
                "status",
            ],
        }
        result = commonQuery.fetchPaginatedData(
            StockLedger,
            data,
            fieldConfig,
            options,
            request=request,
            tenant_config=True,
        )
        result["items"] = [ledgerWithProductName(item, request) for item in result["items"]]
        return successResponse("Stock ledger retrieved successfully.", data=result)
