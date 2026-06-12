from typing import Optional

from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema
from apps.inventory.schemas import StockAdjustmentIn
from apps.inventory.services import StockAdjustmentService, StockLedgerService


router = Router(tags=["inventory"], auth=auth_bearer)


@router.get("/permissions-check", response=ApiResponse)
@permission_required("inventory_view")
def permissionsCheck(request):
    return successResponse(
        "Inventory permission check passed.",
        data={"module": "inventory", "required_permission": "inventory_view"},
    )


@router.post("/adjustments/", response=ApiResponse)
@permission_required("inventory_adjust")
def createStockAdjustment(request, payload: StockAdjustmentIn):
    return StockAdjustmentService.create(payload.dict(), request)


@router.post("/adjustments/get-transactions", response=ApiResponse)
@permission_required("inventory_view")
def getAllStockAdjustments(request, payload: Optional[dict] = None):
    return StockAdjustmentService.getAll(payload, request)


@router.delete("/adjustments/delete", response=ApiResponse)
@permission_required("inventory_adjust")
def deleteStockAdjustments(request, payload: BulkIdsSchema):
    return StockAdjustmentService.delete(payload.dict(), request)


@router.patch("/adjustments/status", response=ApiResponse)
@permission_required("inventory_adjust")
def updateStockAdjustmentStatus(request, payload: StatusUpdateSchema):
    return StockAdjustmentService.updateStatus(payload.dict(), request)


@router.get("/adjustments/{adjustment_id}", response=ApiResponse)
@permission_required("inventory_view")
def getStockAdjustmentById(request, adjustment_id: int):
    return StockAdjustmentService.getById(adjustment_id, request)


@router.post("/ledger/get-transactions", response=ApiResponse)
@permission_required("inventory_view")
def getAllStockLedger(request, payload: Optional[dict] = None):
    return StockLedgerService.getAll(payload, request)
