# type: ignore
from django.utils import timezone

from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.responses import successResponse
from apps.notifications.models import Notification


class NotificationService:
    @staticmethod
    def create(data, request):
        notification = commonQuery.createRecord(Notification, data, request=request, tenant_config=True)
        return successResponse("Notification created successfully.", data=notification)

    @staticmethod
    def push(*, title, message="", notification_type="info", source_type="system", source_id=None, user_id=None, action_url="", payload=None, request=None):
        return commonQuery.createRecord(
            Notification,
            {
                "user_id": user_id,
                "title": title,
                "message": message,
                "notification_type": notification_type,
                "source_type": source_type,
                "source_id": source_id,
                "action_url": action_url,
                "payload": payload or {},
            },
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            Notification,
            data,
            [["title", True, True], ["message", True, True], ["notification_type", True, True], ["source_type", True, True]],
            {
                "attributes": [
                    "id",
                    "user_id",
                    "user__full_name",
                    "title",
                    "message",
                    "notification_type",
                    "source_type",
                    "source_id",
                    "action_url",
                    "is_read",
                    "read_at",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Notifications retrieved successfully.", data=result)

    @staticmethod
    def unreadCount(request):
        count = Notification.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
            is_read=False,
        ).filter(user_id__in=[request.user.id, None]).count()
        return successResponse("Unread notification count retrieved successfully.", data={"count": count})

    @staticmethod
    def markRead(data, request):
        ids = data.get("ids")
        if not isinstance(ids, list):
            ids = [ids]
        count = Notification.objects.filter(
            id__in=ids,
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
        ).update(is_read=True, read_at=timezone.now())
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Notification not found.")
        return successResponse("Notifications marked as read successfully.", data={"updated_count": count})

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Notification, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Notification not found.")
        return successResponse("Notifications deleted successfully.")
