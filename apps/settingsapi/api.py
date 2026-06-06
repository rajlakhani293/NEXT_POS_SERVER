from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.settingsapi.schemas import BusinessSettingIn
from apps.settingsapi.services import BusinessSettingService


router = Router(tags=["settings"], auth=auth_bearer)


@router.get("/business", response=ApiResponse)
@permission_required("settings_view")
def getBusinessSettings(request):
    return BusinessSettingService.get(request.user)


@router.put("/business", response=ApiResponse)
@permission_required("settings_update")
def updateBusinessSettings(request, payload: BusinessSettingIn):
    return BusinessSettingService.update(request.user, payload.dict())
