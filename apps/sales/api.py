from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.sales.schemas import SaleCreateIn, SaleListIn, SaleReturnCreateIn
from apps.sales.services import SaleService


router = Router(tags=["sales"], auth=auth_bearer)


@router.post("/", response=ApiResponse)
@permission_required("sales_create")
def createSale(request, payload: SaleCreateIn):
    return SaleService.create(payload.dict(), request)


@router.post("/get-transactions", response=ApiResponse)
@permission_required("sales_view")
def listSales(request, payload: SaleListIn):
    return SaleService.listSales(payload.dict(), request)


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
