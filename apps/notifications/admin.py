from django.contrib import admin

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "identifier", "source", "user", "dismissable", "status", "created_at")
    list_filter = ("source", "dismissable", "status")
    search_fields = ("title", "description", "identifier")
