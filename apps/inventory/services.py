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


STOCK_INCREASE_ACTIONS = ["added"]
STOCK_REDUCE_ACTIONS = ["deleted", "defective", "lost"]
STOCK_SET_ACTION = "set"
STOCK_ADJUSTMENT_LABELS = {
    "added": "Add",
    "deleted": "Delete",
    "defective": "Defective",
    "lost": "Lost",
    "set": "Set",
}


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
        supported_actions = STOCK_INCREASE_ACTIONS + STOCK_REDUCE_ACTIONS + [STOCK_SET_ACTION]
        if adjustment_type not in supported_actions:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unsupported stock adjustment action.")

        adjustment_qty = decimalValue(data.get("quantity"))
        if adjustment_qty < 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Adjustment quantity cannot be negative.")
        if adjustment_type != STOCK_SET_ACTION and adjustment_qty == 0:
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
            if adjustment_type in STOCK_REDUCE_ACTIONS and current_stock < adjustment_qty:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Insufficient stock for adjustment.")

            if adjustment_type in STOCK_INCREASE_ACTIONS:
                stock_delta = adjustment_qty
                new_stock = current_stock + adjustment_qty
                ledger_entry_type = "adjustment_in"
            elif adjustment_type in STOCK_REDUCE_ACTIONS:
                stock_delta = adjustment_qty * Decimal("-1")
                new_stock = current_stock - adjustment_qty
                ledger_entry_type = "adjustment_out"
            else:
                stock_delta = adjustment_qty - current_stock
                new_stock = adjustment_qty
                ledger_entry_type = "adjustment_set"

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
            if adjustment_type == STOCK_SET_ACTION:
                Product.objects.filter(id=product["id"]).update(current_stock=new_stock)
            else:
                Product.objects.filter(id=product["id"]).update(current_stock=F("current_stock") + stock_delta)

            ledger = commonQuery.createRecord(
                StockLedger,
                {
                    "product_id": product["id"],
                    "entry_type": ledger_entry_type,
                    "quantity": stock_delta,
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
            adjustment["stock_delta"] = stock_delta
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
        for item in result["items"]:
            item["adjustment_type_label"] = STOCK_ADJUSTMENT_LABELS.get(item.get("adjustment_type"), item.get("adjustment_type"))
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
