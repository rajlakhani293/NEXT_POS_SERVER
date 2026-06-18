from typing import Optional
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.common.schemas import BulkIdsSchema
from apps.notifications.schemas import NotificationIn
from apps.notifications.services import NotificationService


router = Router(tags=["notifications"], auth=auth_bearer)


@router.post("/", response=ApiResponse)
@permission_required("settings_update")
def createNotification(request, payload: NotificationIn):
    return NotificationService.create(payload.dict(), request)


@router.post("/get-transactions", response=ApiResponse)
@permission_required("settings_view")
def getNotifications(request, payload: Optional[dict] = None):
    return NotificationService.getAll(payload, request)


@router.get("/unread-count", response=ApiResponse)
def unreadCount(request):
    return NotificationService.unreadCount(request)


@router.patch("/mark-read", response=ApiResponse)
def markRead(request, payload: BulkIdsSchema):
    return NotificationService.markRead(payload.dict(), request)


@router.delete("/delete", response=ApiResponse)
@permission_required("settings_update")
def deleteNotifications(request, payload: BulkIdsSchema):
    return NotificationService.delete(payload.dict(), request)
