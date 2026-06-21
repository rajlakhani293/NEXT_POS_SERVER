from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema
from apps.sales.schemas import (
    InstallmentPayIn,
    OrderInstalmentUpdateIn,
    OrderInstalmentsCreateIn,
    SaleCollectDueIn,
    SaleCreateIn,
    SaleHoldIn,
    SaleListIn,
    SaleReturnCreateIn,
    SaleStatusUpdateIn,
    SaleVoidIn,
)
from apps.sales.services import SaleService


router = Router(tags=["sales"], auth=auth_bearer)


@router.post("/", response=ApiResponse)
@permission_required("sales_create")
def createSale(request, payload: SaleCreateIn):
    return SaleService.create(payload.dict(), request)


@router.post("/hold", response=ApiResponse)
@permission_required("sales_create")
def holdSale(request, payload: SaleHoldIn):
    return SaleService.hold(payload.dict(), request)


@router.post("/get-transactions", response=ApiResponse)
@permission_required("sales_view")
def listSales(request, payload: SaleListIn):
    return SaleService.listSales(payload.dict(), request)


@router.delete("/delete", response=ApiResponse)
@permission_required("sales_delete")
def deleteSales(request, payload: BulkIdsSchema):
    return SaleService.delete(payload.dict(), request)


@router.post("/drafts/get-transactions", response=ApiResponse)
@permission_required("sales_view")
def listHeldSales(request, payload: SaleListIn):
    return SaleService.listHeldCarts(payload.dict(), request)


@router.get("/drafts/{draft_id}", response=ApiResponse)
@permission_required("sales_view")
def getHeldSale(request, draft_id: int):
    return SaleService.getHeldCart(draft_id, request)


@router.delete("/drafts/{draft_id}", response=ApiResponse)
@permission_required("sales_update")
def deleteHeldSale(request, draft_id: int):
    return SaleService.deleteHeldCart(draft_id, request)


@router.post("/drafts/clear-expired", response=ApiResponse)
@permission_required("sales_update")
def clearExpiredHeldSales(request):
    return SaleService.enqueueClearExpiredHeldCarts({}, request)


@router.post("/storage/purge", response=ApiResponse)
@permission_required("sales_update")
def purgeOrderStorage(request):
    return SaleService.enqueuePurgeOrderStorage({}, request)


@router.get("/{sale_order_id}", response=ApiResponse)
@permission_required("sales_view")
def getSale(request, sale_order_id: int):
    return SaleService.getSale(sale_order_id, request)


@router.get("/{sale_order_id}/receipt", response=ApiResponse)
@permission_required("sales_view")
def getSaleReceipt(request, sale_order_id: int):
    return SaleService.getReceipt(sale_order_id, request)


@router.post("/{sale_order_id}/refund", response=ApiResponse)
@permission_required("refund_order")
def createSaleReturn(request, sale_order_id: int, payload: SaleReturnCreateIn):
    return SaleService.createReturn(sale_order_id, payload.dict(), request)


@router.post("/{sale_order_id}/void", response=ApiResponse)
@permission_required("sales_void")
def voidSale(request, sale_order_id: int, payload: SaleVoidIn):
    return SaleService.void(sale_order_id, payload.dict(), request)


@router.post("/{sale_order_id}/collect-due", response=ApiResponse)
@permission_required("payments_collect_due")
def collectSaleDue(request, sale_order_id: int, payload: SaleCollectDueIn):
    return SaleService.collectDue(sale_order_id, payload.dict(), request)


@router.post("/{sale_order_id}/processing", response=ApiResponse)
@permission_required("sales_update")
def updateSaleProcessing(request, sale_order_id: int, payload: SaleStatusUpdateIn):
    return SaleService.updateProcessingStatus(sale_order_id, payload.dict(), request)


@router.post("/{sale_order_id}/delivery", response=ApiResponse)
@permission_required("sales_update")
def updateSaleDelivery(request, sale_order_id: int, payload: SaleStatusUpdateIn):
    return SaleService.updateDeliveryStatus(sale_order_id, payload.dict(), request)


@router.get("/{sale_order_id}/instalments", response=ApiResponse)
@permission_required("sales_view")
def getSaleInstallments(request, sale_order_id: int):
    return SaleService.getInstallments(sale_order_id, request)


@router.post("/{sale_order_id}/instalments", response=ApiResponse)
@permission_required("sales_update")
def createSaleInstallments(request, sale_order_id: int, payload: OrderInstalmentsCreateIn):
    return SaleService.createInstallments(sale_order_id, payload.dict(), request)


@router.put("/{sale_order_id}/instalments/{installment_id}", response=ApiResponse)
@permission_required("sales_update")
def updateSaleInstallment(
    request,
    sale_order_id: int,
    installment_id: int,
    payload: OrderInstalmentUpdateIn,
):
    return SaleService.updateInstallment(sale_order_id, installment_id, payload.dict(exclude_none=True), request)


@router.delete("/{sale_order_id}/instalments/{installment_id}", response=ApiResponse)
@permission_required("sales_update")
def deleteSaleInstallment(request, sale_order_id: int, installment_id: int):
    return SaleService.deleteInstallment(sale_order_id, installment_id, request)


@router.post("/{sale_order_id}/instalments/{installment_id}/pay", response=ApiResponse)
@permission_required("payments_create")
def paySaleInstallment(
    request,
    sale_order_id: int,
    installment_id: int,
    payload: InstallmentPayIn,
):
    return SaleService.payInstallment(sale_order_id, installment_id, payload.dict(), request)


@router.get("/{sale_order_id}/refunds", response=ApiResponse)
@permission_required("returns_view")
def getSaleRefunds(request, sale_order_id: int):
    return SaleService.getRefunds(sale_order_id, request)


@router.get("/{sale_order_id}/products/refunded", response=ApiResponse)
@permission_required("returns_view")
def getSaleRefundedProducts(request, sale_order_id: int):
    return SaleService.getRefundedItems(sale_order_id, request)


@router.get("/permissions-check", response=ApiResponse)
@permission_required("sales_view")
def permissionsCheck(request):
    return successResponse(
        "Sales permission check passed.",
        data={"module": "sales", "required_permission": "sales_view"},
    )
