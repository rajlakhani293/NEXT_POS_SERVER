from django.contrib import admin

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "notification_type", "source_type", "user", "is_read", "status", "created_at")
    list_filter = ("notification_type", "source_type", "is_read", "status")
    search_fields = ("title", "message")
