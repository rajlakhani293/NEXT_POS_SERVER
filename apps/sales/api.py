# type: ignore
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema, payloadData
from apps.sales.schemas import (
    InstallmentPayIn,
    OrderPaymentActionIn,
    OrderProductsActionIn,
    OrderInstalmentPayloadIn,
    OrderInstalmentUpdateIn,
    OrderInstalmentsCreateIn,
    SaleCollectDueIn,
    SaleCreateIn,
    SaleHoldIn,
    SaleListIn,
    SaleReturnCreateIn,
    SaleStatusUpdateIn,
    SaleUpdateIn,
    SaleVoidIn,
)
from apps.sales.services import SaleService


router = Router(tags=["sales"], auth=auth_bearer)
ordersRouter = Router(tags=["orders"], auth=auth_bearer)


@router.post("/", response=ApiResponse)
@permissionRequired("pos.create.orders")
def createSale(request, payload: SaleCreateIn):
    return SaleService.create(payloadData(payload), request)


@router.post("/hold", response=ApiResponse)
@permissionRequired("pos.create.orders")
def holdSale(request, payload: SaleHoldIn):
    return SaleService.hold(payloadData(payload), request)


@router.post("/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.orders")
def listSales(request, payload: SaleListIn):
    return SaleService.listSales(payloadData(payload), request)


@router.delete("/delete", response=ApiResponse)
@permissionRequired("pos.delete.orders")
def deleteSales(request, payload: BulkIdsSchema):
    return SaleService.delete(payloadData(payload), request)


@router.post("/drafts/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.orders")
def listHeldSales(request, payload: SaleListIn):
    return SaleService.listHeldCarts(payloadData(payload), request)


@router.get("/drafts/{draft_id}", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getHeldSale(request, draft_id: int):
    return SaleService.getHeldCart(draft_id, request)


@router.delete("/drafts/{draft_id}", response=ApiResponse)
@permissionRequired("pos.update.orders")
def deleteHeldSale(request, draft_id: int):
    return SaleService.deleteHeldCart(draft_id, request)


@router.post("/drafts/clear-expired", response=ApiResponse)
@permissionRequired("pos.update.orders")
def clearExpiredHeldSales(request):
    return SaleService.enqueueClearExpiredHeldCarts({}, request)


@router.post("/storage/purge", response=ApiResponse)
@permissionRequired("pos.update.orders")
def purgeOrderStorage(request):
    return SaleService.enqueuePurgeOrderStorage({}, request)


@router.post("/layaway/track-expired", response=ApiResponse)
@permissionRequired("pos.update.orders")
def trackExpiredLaidAway(request):
    return SaleService.enqueueTrackLaidAwayOrders({}, request)


@router.get("/permissions-check", response=ApiResponse)
@permissionRequired("pos.read.orders")
def permissionsCheck(request):
    return successResponse(
        "Sales permission check passed.",
        data={"module": "sales", "required_permission": "sales_view"},
    )


@router.get("/pos/session", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getPosSession(request):
    return SaleService.getPosSession(request)


@router.get("/{sale_order_id}", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getSale(request, sale_order_id: int):
    return SaleService.getSale(sale_order_id, request)


@router.put("/{sale_order_id}", response=ApiResponse)
@permissionRequired("pos.update.orders")
def updateSale(request, sale_order_id: int, payload: SaleUpdateIn):
    return SaleService.update(sale_order_id, payloadData(payload), request)


@router.get("/{sale_order_id}/receipt", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getSaleReceipt(request, sale_order_id: int):
    return SaleService.getReceipt(sale_order_id, request)


@router.post("/{sale_order_id}/refund", response=ApiResponse)
@permissionRequired("pos.refund.orders")
def createSaleReturn(request, sale_order_id: int, payload: SaleReturnCreateIn):
    return SaleService.createReturn(sale_order_id, payloadData(payload), request)


@router.post("/{sale_order_id}/void", response=ApiResponse)
@permissionRequired("pos.void.orders")
def voidSale(request, sale_order_id: int, payload: SaleVoidIn):
    return SaleService.void(sale_order_id, payloadData(payload), request)


@router.post("/{sale_order_id}/collect-due", response=ApiResponse)
@permissionRequired("pos.make-payment.orders")
def collectSaleDue(request, sale_order_id: int, payload: SaleCollectDueIn):
    return SaleService.collectDue(sale_order_id, payloadData(payload), request)


@router.post("/{sale_order_id}/processing", response=ApiResponse)
@permissionRequired("pos.update.orders")
def updateSaleProcessing(request, sale_order_id: int, payload: SaleStatusUpdateIn):
    return SaleService.updateProcessingStatus(sale_order_id, payloadData(payload), request)


@router.post("/{sale_order_id}/delivery", response=ApiResponse)
@permissionRequired("pos.update.orders")
def updateSaleDelivery(request, sale_order_id: int, payload: SaleStatusUpdateIn):
    return SaleService.updateDeliveryStatus(sale_order_id, payloadData(payload), request)


@router.get("/{sale_order_id}/instalments", response=ApiResponse)
@permissionRequired("pos.read.orders-instalments")
def getSaleInstallments(request, sale_order_id: int):
    return SaleService.getInstallments(sale_order_id, request)


@router.post("/{sale_order_id}/instalments", response=ApiResponse)
@permissionRequired("pos.create.orders-instalments")
def createSaleInstallments(request, sale_order_id: int, payload: OrderInstalmentsCreateIn):
    return SaleService.createInstallments(sale_order_id, payloadData(payload), request)


@router.put("/{sale_order_id}/instalments/{installment_id}", response=ApiResponse)
@permissionRequired("pos.update.orders-instalments")
def updateSaleInstallment(
    request,
    sale_order_id: int,
    installment_id: int,
    payload: OrderInstalmentUpdateIn,
):
    return SaleService.updateInstallment(sale_order_id, installment_id, payloadData(payload, exclude_none=True), request)


@router.delete("/{sale_order_id}/instalments/{installment_id}", response=ApiResponse)
@permissionRequired("pos.delete.orders-instalments")
def deleteSaleInstallment(request, sale_order_id: int, installment_id: int):
    return SaleService.deleteInstallment(sale_order_id, installment_id, request)


@router.post("/{sale_order_id}/instalments/{installment_id}/pay", response=ApiResponse)
@permissionRequired("pos.update.orders-instalments")
def paySaleInstallment(
    request,
    sale_order_id: int,
    installment_id: int,
    payload: InstallmentPayIn,
):
    return SaleService.payInstallment(sale_order_id, installment_id, payloadData(payload), request)


@router.get("/{sale_order_id}/refunds", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getSaleRefunds(request, sale_order_id: int):
    return SaleService.getRefunds(sale_order_id, request)


@router.get("/refunds/{refund_id}/receipt", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getSaleRefundReceipt(request, refund_id: int):
    return SaleService.getRefundReceipt(refund_id, request)


@router.get("/{sale_order_id}/products/refunded", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getSaleRefundedProducts(request, sale_order_id: int):
    return SaleService.getRefundedItems(sale_order_id, request)


@ordersRouter.get("/payments", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getSupportedOrderPayments(request):
    return SaleService.getSupportedPayments(request)


@ordersRouter.get("/invoice/{order_id}", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getOrderInvoice(request, order_id: int):
    return SaleService.getOrderInvoice(order_id, request)


@ordersRouter.get("/receipt/{order_id}", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getOrderReceipt(request, order_id: int):
    return SaleService.getOrderReceipt(order_id, request)


@ordersRouter.get("/refund-receipt/{refund_id}", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getOrderRefundReceipt(request, refund_id: int):
    return SaleService.getRefundReceipt(refund_id, request)


@ordersRouter.get("/payment-receipt/{payment_id}", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getOrderPaymentReceipt(request, payment_id: int):
    return SaleService.getOrderPaymentReceipt(payment_id, request)


@ordersRouter.get("/", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getOrders(request, limit: int = 0):
    data = {"limit": limit} if limit else {}
    return SaleService.getOrderCollection(data, request)


@ordersRouter.get("/{order_id}", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getOrder(request, order_id: int):
    return SaleService.getSale(order_id, request)


@ordersRouter.get("/{order_id}/pos", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getPosOrder(request, order_id: int):
    return SaleService.getSale(order_id, request)


@ordersRouter.get("/{order_id}/products", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getOrderProducts(request, order_id: int):
    return SaleService.getOrderProducts(order_id, request)


@ordersRouter.get("/{order_id}/products/refunded", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getOrderProductsRefunded(request, order_id: int):
    return SaleService.getRefundedItems(order_id, request)


@ordersRouter.get("/{order_id}/refunds", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getOrderRefunds(request, order_id: int):
    return SaleService.getOrderRefunds(order_id, request)


@ordersRouter.get("/{order_id}/payments", response=ApiResponse)
@permissionRequired("pos.read.orders")
def getOrderPayments(request, order_id: int):
    return SaleService.getOrderPayments(order_id, request)


@ordersRouter.get("/{order_id}/instalments", response=ApiResponse)
@permissionRequired("pos.read.orders-instalments")
def getOrderInstalments(request, order_id: int):
    return SaleService.getInstallments(order_id, request)


@ordersRouter.get("/{order_id}/print/{doc}", response=ApiResponse)
@permissionRequired("pos.read.orders")
def printOrderDocument(request, order_id: int, doc: str):
    return SaleService.printOrder(order_id, doc, request)


@ordersRouter.get("/{order_id}/print", response=ApiResponse)
@permissionRequired("pos.read.orders")
def printOrder(request, order_id: int):
    return SaleService.printOrder(order_id, "receipt", request)


@ordersRouter.post("/", response=ApiResponse)
@permissionRequired("pos.create.orders")
def createOrder(request, payload: SaleCreateIn):
    return SaleService.create(payloadData(payload), request)


@ordersRouter.put("/{order_id}", response=ApiResponse)
@permissionRequired("pos.update.orders")
def updateOrder(request, order_id: int, payload: SaleUpdateIn):
    return SaleService.update(order_id, payloadData(payload), request)


@ordersRouter.delete("/{order_id}", response=ApiResponse)
@permissionRequired("pos.delete.orders")
def deleteOrder(request, order_id: int):
    return SaleService.delete({"ids": [order_id]}, request)


@ordersRouter.post("/{order_id}/products", response=ApiResponse)
@permissionRequired("pos.update.orders")
def addProductToOrder(request, order_id: int, payload: OrderProductsActionIn):
    return SaleService.addProducts(order_id, payloadData(payload).get("products") or [], request)


@ordersRouter.delete("/{order_id}/products/{product_id}", response=ApiResponse)
@permissionRequired("pos.update.orders")
def deleteOrderProduct(request, order_id: int, product_id: int):
    return SaleService.deleteOrderProduct(order_id, product_id, request)


@ordersRouter.post("/{order_id}/processing", response=ApiResponse)
@permissionRequired("pos.update.orders")
def changeOrderProcessingStatus(request, order_id: int, payload: dict):
    data = payloadData(payload)
    return SaleService.updateProcessingStatus(order_id, {"status": data.get("status") or data.get("process_status"), "note": data.get("note") or ""}, request)


@ordersRouter.post("/{order_id}/delivery", response=ApiResponse)
@permissionRequired("pos.update.orders")
def changeOrderDeliveryStatus(request, order_id: int, payload: dict):
    data = payloadData(payload)
    return SaleService.updateDeliveryStatus(order_id, {"status": data.get("status") or data.get("delivery_status"), "note": data.get("note") or ""}, request)


@ordersRouter.post("/{order_id}/payments", response=ApiResponse)
@permissionRequired("pos.make-payment.orders")
def addOrderPayment(request, order_id: int, payload: OrderPaymentActionIn):
    return SaleService.addPayment(order_id, payloadData(payload, exclude_none=True), request)


@ordersRouter.post("/{order_id}/refund", response=ApiResponse)
@permissionRequired("pos.refund.orders")
def makeOrderRefund(request, order_id: int, payload: SaleReturnCreateIn):
    return SaleService.refundOrder(order_id, payloadData(payload), request)


@ordersRouter.post("/{order_id}/void", response=ApiResponse)
@permissionRequired("pos.void.orders")
def voidOrder(request, order_id: int, payload: SaleVoidIn):
    return SaleService.voidOrder(order_id, payloadData(payload), request)


@ordersRouter.post("/{order_id}/instalments", response=ApiResponse)
@permissionRequired("pos.create.orders-instalments")
def createOrderInstalment(request, order_id: int, payload: OrderInstalmentsCreateIn):
    data = payloadData(payload)
    if data.get("instalment"):
        return SaleService.createInstallment(order_id, data["instalment"], request)
    return SaleService.createInstallments(order_id, data, request)


@ordersRouter.put("/{order_id}/instalments/{installment_id}", response=ApiResponse)
@permissionRequired("pos.update.orders-instalments")
def updateOrderInstalment(request, order_id: int, installment_id: int, payload: OrderInstalmentPayloadIn):
    return SaleService.updateInstallment(order_id, installment_id, payloadData(payload, exclude_none=True), request)


@ordersRouter.delete("/{order_id}/instalments/{installment_id}", response=ApiResponse)
@permissionRequired("pos.delete.orders-instalments")
def deleteOrderInstalment(request, order_id: int, installment_id: int):
    return SaleService.deleteInstallment(order_id, installment_id, request)


@ordersRouter.post("/{order_id}/instalments/{installment_id}/pay", response=ApiResponse)
@permissionRequired("pos.update.orders-instalments")
def payOrderInstalment(request, order_id: int, installment_id: int, payload: InstallmentPayIn):
    return SaleService.payInstallment(order_id, installment_id, payloadData(payload), request)
