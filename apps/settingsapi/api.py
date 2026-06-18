from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.settingsapi.schemas import OptionSettingIn
from apps.settingsapi.services import OptionSettingService


router = Router(tags=["settings"], auth=auth_bearer)


@router.get("/business", response=ApiResponse)
@permission_required("settings_view")
def getOptionSettings(request):
    return OptionSettingService.get(request.user)


@router.put("/business", response=ApiResponse)
@permission_required("settings_update")
def updateOptionSettings(request, payload: OptionSettingIn):
    return OptionSettingService.update(request.user, payload.dict())
