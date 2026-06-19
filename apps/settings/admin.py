from django.contrib import admin

from apps.settings.models import FailedJob, Job, Media, Notification, Option, PaymentType


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "company", "branch", "status")
    list_filter = ("status", "array")
    search_fields = ("key", "value")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "queue", "company", "branch", "status")
    list_filter = ("status", "queue")
    search_fields = ("queue", "payload")


@admin.register(FailedJob)
class FailedJobAdmin(admin.ModelAdmin):
    list_display = ("id", "queue", "company", "branch", "status", "failed_at")
    list_filter = ("status",)
    search_fields = ("queue", "payload", "exception")


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "extension", "company", "branch", "status")
    list_filter = ("status", "extension")
    search_fields = ("name", "slug")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "source", "company", "branch", "status")
    list_filter = ("status", "source")
    search_fields = ("title", "description", "identifier")


@admin.register(PaymentType)
class PaymentTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "identifier", "readonly", "company", "branch", "status")
    list_filter = ("status", "readonly")
    search_fields = ("label", "identifier")
