from typing import Optional

from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData
from apps.purchases.schemas import (
    PurchaseItemIn,
    PurchaseItemUpdateIn,
    PurchaseOrderIn,
    PurchaseOrderUpdateIn,
    PurchaseProductsBulkUpdateIn,
    PurchaseReceiveIn,
    PurchaseStatusIn,
    SupplierIn,
    SupplierUpdateIn,
)
from apps.purchases.services import PurchaseOrderService, SupplierService


router = Router(tags=["purchases"], auth=auth_bearer)


@router.post("/suppliers/", response=ApiResponse)
@permission_required("purchases_create")
def createSupplier(request, payload: SupplierIn):
    return SupplierService.create(payloadData(payload), request)


@router.post("/suppliers/get-transactions", response=ApiResponse)
@permission_required("purchases_view")
def getAllSuppliers(request, payload: Optional[dict] = None):
    return SupplierService.getAll(payload, request)


@router.get("/suppliers/dropdown-list", response=ApiResponse)
@permission_required("purchases_view")
def getSupplierDropdown(request):
    return SupplierService.dropdownList(request)


@router.delete("/suppliers/delete", response=ApiResponse)
@permission_required("purchases_delete")
def deleteSuppliers(request, payload: BulkIdsSchema):
    return SupplierService.delete(payloadData(payload), request)


@router.patch("/suppliers/status", response=ApiResponse)
@permission_required("purchases_update")
def updateSupplierStatus(request, payload: StatusUpdateSchema):
    return SupplierService.updateStatus(payloadData(payload), request)


@router.get("/suppliers/{supplier_id}", response=ApiResponse)
@permission_required("purchases_view")
def getSupplierById(request, supplier_id: int):
    return SupplierService.getById(supplier_id, request)


@router.put("/suppliers/{supplier_id}", response=ApiResponse)
@permission_required("purchases_update")
def updateSupplier(request, supplier_id: int, payload: SupplierUpdateIn):
    return SupplierService.update(supplier_id, payloadData(payload, exclude_none=True), request)


@router.post("/orders/", response=ApiResponse)
@permission_required("purchases_create")
def createPurchaseOrder(request, payload: PurchaseOrderIn):
    return PurchaseOrderService.create(payloadData(payload), request)


@router.post("/orders/get-transactions", response=ApiResponse)
@permission_required("purchases_view")
def getAllPurchaseOrders(request, payload: Optional[dict] = None):
    return PurchaseOrderService.getAll(payload, request)


@router.post("/products/get-transactions", response=ApiResponse)
@permission_required("purchases_view")
def getAllProcurementProducts(request, payload: Optional[dict] = None):
    return PurchaseOrderService.getProducts(payload, request)


@router.delete("/orders/delete", response=ApiResponse)
@permission_required("purchases_delete")
def deletePurchaseOrders(request, payload: BulkIdsSchema):
    return PurchaseOrderService.delete(payloadData(payload), request)


@router.get("/orders/{order_id}", response=ApiResponse)
@permission_required("purchases_view")
def getPurchaseOrderById(request, order_id: int):
    return PurchaseOrderService.getById(order_id, request)


@router.get("/orders/{order_id}/products", response=ApiResponse)
@permission_required("purchases_view")
def getPurchaseOrderProducts(request, order_id: int):
    return PurchaseOrderService.getOrderProducts(order_id, request)


@router.get("/orders/{order_id}/refresh", response=ApiResponse)
@permission_required("purchases_view")
def refreshPurchaseOrder(request, order_id: int):
    return PurchaseOrderService.refresh(order_id, request)


@router.post("/orders/{order_id}/queue-refresh", response=ApiResponse)
@permission_required("purchases_update")
def queueRefreshPurchaseOrder(request, order_id: int):
    return PurchaseOrderService.enqueueRefresh(order_id, request)


@router.put("/orders/{order_id}", response=ApiResponse)
@permission_required("purchases_update")
def updatePurchaseOrder(request, order_id: int, payload: PurchaseOrderUpdateIn):
    return PurchaseOrderService.update(order_id, payloadData(payload, exclude_none=True), request)


@router.put("/orders/{order_id}/change-payment-status", response=ApiResponse)
@permission_required("purchases_update")
def changePurchaseStatus(request, order_id: int, payload: PurchaseStatusIn):
    return PurchaseOrderService.changePaymentStatus(order_id, payloadData(payload, exclude_none=True), request)


@router.post("/orders/{order_id}/products", response=ApiResponse)
@permission_required("purchases_create")
def addPurchaseOrderProduct(request, order_id: int, payload: PurchaseItemIn):
    return PurchaseOrderService.addProduct(order_id, payloadData(payload), request)


@router.put("/orders/{order_id}/products/{purchase_item_id}", response=ApiResponse)
@permission_required("purchases_update")
def updatePurchaseOrderProduct(request, order_id: int, purchase_item_id: int, payload: PurchaseItemUpdateIn):
    return PurchaseOrderService.editProduct(order_id, purchase_item_id, payloadData(payload, exclude_none=True), request)


@router.put("/orders/{order_id}/products", response=ApiResponse)
@permission_required("purchases_update")
def bulkUpdatePurchaseOrderProducts(request, order_id: int, payload: PurchaseProductsBulkUpdateIn):
    return PurchaseOrderService.bulkUpdateProducts(order_id, payloadData(payload), request)


@router.delete("/orders/{order_id}/products/{purchase_item_id}", response=ApiResponse)
@permission_required("purchases_delete")
def deletePurchaseOrderProduct(request, order_id: int, purchase_item_id: int):
    return PurchaseOrderService.deleteProduct(order_id, purchase_item_id, request)


@router.post("/orders/{order_id}/receive", response=ApiResponse)
@permission_required("purchases_receive")
def receivePurchaseOrder(request, order_id: int, payload: PurchaseReceiveIn):
    return PurchaseOrderService.receive(order_id, payloadData(payload), request)


@router.get("/orders/{order_id}/set-as-paid", response=ApiResponse)
@permission_required("purchases_update")
def setPurchaseOrderAsPaid(request, order_id: int):
    return PurchaseOrderService.setAsPaid(order_id, request)


@router.get("/preload/{preload_key}", response=ApiResponse)
@permission_required("purchases_view")
def getPurchasePreload(request, preload_key: str):
    return PurchaseOrderService.getPreload(preload_key, request)


@router.post("/preload", response=ApiResponse)
@permission_required("purchases_create")
def storePurchasePreload(request, payload: Optional[dict] = None):
    return PurchaseOrderService.storePreload(payload, request)


@router.get("/low-stock-suggestions", response=ApiResponse)
@permission_required("purchases_view")
def getLowStockSuggestions(request):
    return PurchaseOrderService.lowStockSuggestions(request)


@router.post("/stock-awaiting", response=ApiResponse)
@permission_required("purchases_update")
def stockAwaitingProcurements(request):
    return PurchaseOrderService.stockAwaitingProcurements(request)


@router.post("/stock-awaiting/queue", response=ApiResponse)
@permission_required("purchases_update")
def queueStockAwaitingProcurements(request, payload: Optional[dict] = None):
    return PurchaseOrderService.enqueueStockAwaiting(payload, request)


@router.post("/products/search-product", response=ApiResponse)
@permission_required("purchases_create")
def searchPurchaseProduct(request, payload: Optional[dict] = None):
    return PurchaseOrderService.searchProduct(payload, request)


@router.post("/products/search-procurement-product", response=ApiResponse)
@permission_required("purchases_create")
def searchProcurementProduct(request, payload: Optional[dict] = None):
    return PurchaseOrderService.searchProcurementProduct(payload, request)
