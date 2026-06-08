# type: ignore
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.responses import successResponse
from apps.mediahub.models import Media


class MediaService:
    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    MAX_FILE_SIZE = 5 * 1024 * 1024

    @staticmethod
    def upload(file, request, folder="general", entity_type="", entity_id=None, alt_text=""):
        if not file:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "File is required.")
        if getattr(file, "size", 0) > MediaService.MAX_FILE_SIZE:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "File size must be 5MB or less.")
        content_type = getattr(file, "content_type", "") or ""
        if content_type and content_type not in MediaService.ALLOWED_IMAGE_TYPES:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Only image files are allowed.")

        storage = FileSystemStorage(location=settings.UPLOAD_ROOT, base_url=settings.UPLOAD_URL)
        saved_path = storage.save(f"{folder}/{file.name}", file)
        media = commonQuery.createRecord(
            Media,
            {
                "file_name": Path(saved_path).name,
                "original_name": file.name,
                "file_url": request.build_absolute_uri(storage.url(saved_path)),
                "file_path": saved_path,
                "mime_type": content_type,
                "file_size": getattr(file, "size", 0) or 0,
                "folder": folder,
                "alt_text": alt_text or "",
                "entity_type": entity_type or "",
                "entity_id": entity_id,
                "uploaded_by_id": request.user.id,
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Media uploaded successfully.", data=media)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            Media,
            data,
            [["original_name", True, True], ["folder", True, True], ["entity_type", True, True]],
            {
                "attributes": [
                    "id",
                    "original_name",
                    "file_name",
                    "file_url",
                    "mime_type",
                    "file_size",
                    "folder",
                    "alt_text",
                    "entity_type",
                    "entity_id",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Media retrieved successfully.", data=result)

    @staticmethod
    def update(media_id, data, request):
        updated = commonQuery.updateRecordById(Media, media_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Media not found.")
        return successResponse("Media updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Media, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Media not found.")
        return successResponse("Media deleted successfully.")
