from typing import Optional

from ninja import File, Form, Router, UploadedFile

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.common.schemas import BulkIdsSchema
from apps.mediahub.schemas import MediaUpdateIn
from apps.mediahub.services import MediaService


router = Router(tags=["media"], auth=auth_bearer)


@router.post("/upload", response=ApiResponse)
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


@router.post("/get-transactions", response=ApiResponse)
@permission_required("settings_view")
def getMedia(request, payload: Optional[dict] = None):
    return MediaService.getAll(payload, request)


@router.put("/{media_id}", response=ApiResponse)
@permission_required("settings_update")
def updateMedia(request, media_id: int, payload: MediaUpdateIn):
    return MediaService.update(media_id, payload.dict(exclude_none=True), request)


@router.delete("/delete", response=ApiResponse)
@permission_required("settings_update")
def deleteMedia(request, payload: BulkIdsSchema):
    return MediaService.delete(payload.dict(), request)
