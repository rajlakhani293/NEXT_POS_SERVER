from django.contrib import admin

from apps.mediahub.models import Media


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ("original_name", "folder", "mime_type", "file_size", "entity_type", "entity_id", "status", "created_at")
    list_filter = ("folder", "mime_type", "entity_type", "status")
    search_fields = ("original_name", "file_name", "alt_text")
