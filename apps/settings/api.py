# type: ignore
from typing import Optional
from ninja import File, Form, Router, UploadedFile

from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData
from apps.settings.schemas import (
    MediaUpdateIn,
    NotificationIn,
    OptionSettingIn,
    PaymentTypeCreateIn,
    PaymentTypeListIn,
    PaymentTypeUpdateIn,
    JobListIn,
    FailedJobListIn,
)
from apps.settings.services import JobQueueService, MediaService, NotificationService, OptionSettingService, PaymentTypeService


router = Router(tags=["settings"], auth=auth_bearer)
paymentsRouter = Router(tags=["payments"], auth=auth_bearer)
mediaRouter = Router(tags=["media"], auth=auth_bearer)
notificationsRouter = Router(tags=["notifications"], auth=auth_bearer)


@router.get("/business", response=ApiResponse)
@permissionRequired("settings_view")
def getOptionSettings(request):
    return OptionSettingService.get(request.user)


@router.put("/business", response=ApiResponse)
@permissionRequired("settings_update")
def updateOptionSettings(request, payload: OptionSettingIn):
    return OptionSettingService.update(request.user, payloadData(payload))


@router.post("/jobs/run-next", response=ApiResponse)
@permissionRequired("settings_update")
def runNextJob(request):
    result = JobQueueService.runNext(JobQueueService.handlers())
    return successResponse("Job processed successfully." if result else "No pending job found.", data=result)


@router.post("/jobs/pending/get-transactions", response=ApiResponse)
@permissionRequired("settings_view")
def listPendingJobs(request, payload: JobListIn):
    data = JobQueueService.listPendingJobs(payloadData(payload), request)
    return successResponse("Pending jobs retrieved successfully.", data=data)


@router.post("/jobs/failed/get-transactions", response=ApiResponse)
@permissionRequired("settings_view")
def listFailedJobs(request, payload: FailedJobListIn):
    data = JobQueueService.listFailedJobs(payloadData(payload), request)
    return successResponse("Failed jobs retrieved successfully.", data=data)


@router.post("/jobs/failed/{failed_job_id}/retry", response=ApiResponse)
@permissionRequired("settings_update")
def retryFailedJob(request, failed_job_id: int):
    return JobQueueService.retryFailedJob(failed_job_id, request)


@router.delete("/jobs/failed/{failed_job_id}", response=ApiResponse)
@permissionRequired("settings_update")
def deleteFailedJob(request, failed_job_id: int):
    return JobQueueService.deleteFailedJob(failed_job_id, request)


@paymentsRouter.post("/types/", response=ApiResponse)
@permissionRequired("payments_create")
def createPaymentType(request, payload: PaymentTypeCreateIn):
    return PaymentTypeService.createPaymentType(payloadData(payload), request)


@paymentsRouter.post("/types/get-transactions", response=ApiResponse)
@permissionRequired("payments_view")
def listPaymentTypes(request, payload: PaymentTypeListIn):
    data = PaymentTypeService.listPaymentTypes(payloadData(payload), request)
    return successResponse("Payment types retrieved successfully.", data=data)


@paymentsRouter.get("/types/dropdown-list", response=ApiResponse)
@permissionRequired("payments_view")
def getPaymentTypeDropdown(request):
    return PaymentTypeService.dropdownList(request)


@paymentsRouter.patch("/types/status", response=ApiResponse)
@permissionRequired("payments_update")
def updatePaymentTypeStatus(request, payload: StatusUpdateSchema):
    data = PaymentTypeService.updatePaymentTypeStatus(payloadData(payload), request)
    return successResponse("Payment type status updated successfully.", data=data)


@paymentsRouter.get("/types/{payment_type_id}", response=ApiResponse)
@permissionRequired("payments_view")
def getPaymentType(request, payment_type_id: int):
    data = PaymentTypeService.getPaymentType(payment_type_id, request)
    return successResponse("Payment type retrieved successfully.", data=data)


@paymentsRouter.put("/types/{payment_type_id}", response=ApiResponse)
@permissionRequired("payments_update")
def updatePaymentType(request, payment_type_id: int, payload: PaymentTypeUpdateIn):
    data = PaymentTypeService.updatePaymentType(payment_type_id, payloadData(payload), request)
    return successResponse("Payment type updated successfully.", data=data)


@paymentsRouter.delete("/types/", response=ApiResponse)
@permissionRequired("payments_delete")
def deletePaymentTypes(request, payload: BulkIdsSchema):
    data = PaymentTypeService.deletePaymentTypes(payloadData(payload), request)
    return successResponse("Payment types deleted successfully.", data=data)


@mediaRouter.post("/upload", response=ApiResponse)
@permissionRequired("settings_update")
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
@permissionRequired("settings_view")
def getMedia(request, payload: Optional[dict] = None):
    return MediaService.getAll(payload, request)


@mediaRouter.put("/{media_id}", response=ApiResponse)
@permissionRequired("settings_update")
def updateMedia(request, media_id: int, payload: MediaUpdateIn):
    return MediaService.update(media_id, payloadData(payload, exclude_none=True), request)


@mediaRouter.delete("/delete", response=ApiResponse)
@permissionRequired("settings_update")
def deleteMedia(request, payload: BulkIdsSchema):
    return MediaService.delete(payloadData(payload), request)


@notificationsRouter.post("/", response=ApiResponse)
@permissionRequired("settings_update")
def createNotification(request, payload: NotificationIn):
    return NotificationService.create(payloadData(payload), request)


@notificationsRouter.post("/get-transactions", response=ApiResponse)
@permissionRequired("settings_view")
def getNotifications(request, payload: Optional[dict] = None):
    return NotificationService.getAll(payload, request)


@notificationsRouter.get("/unread-count", response=ApiResponse)
def unreadCount(request):
    return NotificationService.unreadCount(request)


@notificationsRouter.patch("/mark-read", response=ApiResponse)
def markRead(request, payload: BulkIdsSchema):
    return NotificationService.markRead(payloadData(payload), request)


@notificationsRouter.delete("/delete", response=ApiResponse)
@permissionRequired("settings_update")
def deleteNotifications(request, payload: BulkIdsSchema):
    return NotificationService.delete(payloadData(payload), request)


router.add_router("/payments/", paymentsRouter)
router.add_router("/media/", mediaRouter)
router.add_router("/notifications/", notificationsRouter)
