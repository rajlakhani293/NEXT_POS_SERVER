from typing import Optional

from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.purchases.schemas import (
    DeleteSchema,
    PurchaseOrderIn,
    PurchaseOrderUpdateIn,
    PurchasePaymentIn,
    PurchaseReceiveIn,
    StatusUpdateSchema,
    SupplierIn,
    SupplierUpdateIn,
)
from apps.purchases.services import PurchaseOrderService, SupplierService


router = Router(tags=["purchases"], auth=auth_bearer)


@router.post("/suppliers/", response=ApiResponse)
@permission_required("purchases_create")
def createSupplier(request, payload: SupplierIn):
    return SupplierService.create(payload.dict(), request)


@router.post("/suppliers/get-transactions", response=ApiResponse)
@permission_required("purchases_view")
def getAllSuppliers(request, payload: Optional[dict] = None):
    return SupplierService.getAll(payload, request)


@router.get("/suppliers/dropdown-list", response=ApiResponse)
@permission_required("purchases_view")
def getSupplierDropdown(request):
    return SupplierService.dropdownList(request)


@router.delete("/suppliers/delete", response=ApiResponse)
@permission_required("purchases_update")
def deleteSuppliers(request, payload: DeleteSchema):
    return SupplierService.delete(payload.dict(), request)


@router.patch("/suppliers/status", response=ApiResponse)
@permission_required("purchases_update")
def updateSupplierStatus(request, payload: StatusUpdateSchema):
    return SupplierService.updateStatus(payload.dict(), request)


@router.get("/suppliers/{supplier_id}", response=ApiResponse)
@permission_required("purchases_view")
def getSupplierById(request, supplier_id: int):
    return SupplierService.getById(supplier_id, request)


@router.put("/suppliers/{supplier_id}", response=ApiResponse)
@permission_required("purchases_update")
def updateSupplier(request, supplier_id: int, payload: SupplierUpdateIn):
    return SupplierService.update(supplier_id, payload.dict(exclude_none=True), request)


@router.post("/orders/", response=ApiResponse)
@permission_required("purchases_create")
def createPurchaseOrder(request, payload: PurchaseOrderIn):
    return PurchaseOrderService.create(payload.dict(), request)


@router.post("/orders/get-transactions", response=ApiResponse)
@permission_required("purchases_view")
def getAllPurchaseOrders(request, payload: Optional[dict] = None):
    return PurchaseOrderService.getAll(payload, request)


@router.post("/products/get-transactions", response=ApiResponse)
@permission_required("purchases_view")
def getAllProcurementProducts(request, payload: Optional[dict] = None):
    return PurchaseOrderService.getProducts(payload, request)


@router.delete("/orders/delete", response=ApiResponse)
@permission_required("purchases_update")
def deletePurchaseOrders(request, payload: DeleteSchema):
    return PurchaseOrderService.delete(payload.dict(), request)


@router.get("/orders/{order_id}", response=ApiResponse)
@permission_required("purchases_view")
def getPurchaseOrderById(request, order_id: int):
    return PurchaseOrderService.getById(order_id, request)


@router.put("/orders/{order_id}", response=ApiResponse)
@permission_required("purchases_update")
def updatePurchaseOrder(request, order_id: int, payload: PurchaseOrderUpdateIn):
    return PurchaseOrderService.update(order_id, payload.dict(exclude_none=True), request)


@router.post("/orders/{order_id}/receive", response=ApiResponse)
@permission_required("purchases_receive")
def receivePurchaseOrder(request, order_id: int, payload: PurchaseReceiveIn):
    return PurchaseOrderService.receive(order_id, payload.dict(), request)


@router.post("/orders/{order_id}/pay", response=ApiResponse)
@permission_required("purchases_pay")
def payPurchaseOrder(request, order_id: int, payload: PurchasePaymentIn):
    return PurchaseOrderService.pay(order_id, payload.dict(), request)
