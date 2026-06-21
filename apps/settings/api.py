# type: ignore
from typing import Optional
from ninja import File, Form, Router, UploadedFile

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema
from apps.settings.schemas import (
    MediaUpdateIn,
    NotificationIn,
    OptionSettingIn,
    PaymentTypeCreateIn,
    PaymentTypeListIn,
    PaymentTypeUpdateIn,
)
from apps.settings.services import JobQueueService, MediaService, NotificationService, OptionSettingService, PaymentTypeService


router = Router(tags=["settings"], auth=auth_bearer)
paymentsRouter = Router(tags=["payments"], auth=auth_bearer)
mediaRouter = Router(tags=["media"], auth=auth_bearer)
notificationsRouter = Router(tags=["notifications"], auth=auth_bearer)


@router.get("/business", response=ApiResponse)
@permission_required("settings_view")
def getOptionSettings(request):
    return OptionSettingService.get(request.user)


@router.put("/business", response=ApiResponse)
@permission_required("settings_update")
def updateOptionSettings(request, payload: OptionSettingIn):
    return OptionSettingService.update(request.user, payload.dict())


@router.post("/jobs/run-next", response=ApiResponse)
@permission_required("settings_update")
def runNextJob(request):
    from apps.accounting.services import TransactionService
    from apps.catalog.services import CategoryService, ProductStockService
    from apps.customers.services import CustomerAccountService
    from apps.purchases.services import PurchaseOrderService
    from apps.registers.services import RegisterService
    from apps.reports.services import ReportService
    from apps.rewards.services import CustomerRewardService
    from apps.sales.services import SaleService

    handlers = {}
    handlers.update(TransactionService.jobHandlers())
    handlers.update(CategoryService.jobHandlers())
    handlers.update(ProductStockService.jobHandlers())
    handlers.update(CustomerAccountService.jobHandlers())
    handlers.update(PurchaseOrderService.jobHandlers())
    handlers.update(RegisterService.jobHandlers())
    handlers.update(ReportService.jobHandlers())
    handlers.update(CustomerRewardService.jobHandlers())
    handlers.update(SaleService.jobHandlers())
    result = JobQueueService.runNext(handlers)
    return successResponse("Job processed successfully." if result else "No pending job found.", data=result)


@paymentsRouter.post("/types/", response=ApiResponse)
@permission_required("payments_create")
def createPaymentType(request, payload: PaymentTypeCreateIn):
    return PaymentTypeService.createPaymentType(payload.dict(), request)


@paymentsRouter.post("/types/get-transactions", response=ApiResponse)
@permission_required("payments_view")
def listPaymentTypes(request, payload: PaymentTypeListIn):
    data = PaymentTypeService.listPaymentTypes(payload.dict(), request)
    return successResponse("Payment types retrieved successfully.", data=data)


@paymentsRouter.get("/types/dropdown-list", response=ApiResponse)
@permission_required("payments_view")
def getPaymentTypeDropdown(request):
    return PaymentTypeService.dropdownList(request)


@paymentsRouter.patch("/types/status", response=ApiResponse)
@permission_required("payments_update")
def updatePaymentTypeStatus(request, payload: StatusUpdateSchema):
    data = PaymentTypeService.updatePaymentTypeStatus(payload.dict(), request)
    return successResponse("Payment type status updated successfully.", data=data)


@paymentsRouter.get("/types/{payment_type_id}", response=ApiResponse)
@permission_required("payments_view")
def getPaymentType(request, payment_type_id: int):
    data = PaymentTypeService.getPaymentType(payment_type_id, request)
    return successResponse("Payment type retrieved successfully.", data=data)


@paymentsRouter.put("/types/{payment_type_id}", response=ApiResponse)
@permission_required("payments_update")
def updatePaymentType(request, payment_type_id: int, payload: PaymentTypeUpdateIn):
    data = PaymentTypeService.updatePaymentType(payment_type_id, payload.dict(), request)
    return successResponse("Payment type updated successfully.", data=data)


@paymentsRouter.delete("/types/", response=ApiResponse)
@permission_required("payments_delete")
def deletePaymentTypes(request, payload: BulkIdsSchema):
    data = PaymentTypeService.deletePaymentTypes(payload.dict(), request)
    return successResponse("Payment types deleted successfully.", data=data)


@mediaRouter.post("/upload", response=ApiResponse)
@permission_required("settings_update")
def uploadMedia(
    request,
    file: UploadedFile = File(...),
    folder: str = Form("general"),
    entity_type: str = Form(""),
    entity_id: Optional[int] = Form(None),
    alt_text: str = Form(""),
):
    return MediaService.upload(file, request, folder, entity_type, entity_id, alt_text)


@mediaRouter.post("/get-transactions", response=ApiResponse)
@permission_required("settings_view")
def getMedia(request, payload: Optional[dict] = None):
    return MediaService.getAll(payload, request)


@mediaRouter.put("/{media_id}", response=ApiResponse)
@permission_required("settings_update")
def updateMedia(request, media_id: int, payload: MediaUpdateIn):
    return MediaService.update(media_id, payload.dict(exclude_none=True), request)


@mediaRouter.delete("/delete", response=ApiResponse)
@permission_required("settings_update")
def deleteMedia(request, payload: BulkIdsSchema):
    return MediaService.delete(payload.dict(), request)


@notificationsRouter.post("/", response=ApiResponse)
@permission_required("settings_update")
def createNotification(request, payload: NotificationIn):
    return NotificationService.create(payload.dict(), request)


@notificationsRouter.post("/get-transactions", response=ApiResponse)
@permission_required("settings_view")
def getNotifications(request, payload: Optional[dict] = None):
    return NotificationService.getAll(payload, request)


@notificationsRouter.get("/unread-count", response=ApiResponse)
def unreadCount(request):
    return NotificationService.unreadCount(request)


@notificationsRouter.patch("/mark-read", response=ApiResponse)
def markRead(request, payload: BulkIdsSchema):
    return NotificationService.markRead(payload.dict(), request)


@notificationsRouter.delete("/delete", response=ApiResponse)
@permission_required("settings_update")
def deleteNotifications(request, payload: BulkIdsSchema):
    return NotificationService.delete(payload.dict(), request)


router.add_router("/payments/", paymentsRouter)
router.add_router("/media/", mediaRouter)
router.add_router("/notifications/", notificationsRouter)
