from django.contrib import admin

from apps.mediahub.models import Media


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ("name", "extension", "slug", "user", "status", "created_at")
    list_filter = ("extension", "status")
    search_fields = ("name", "slug")
