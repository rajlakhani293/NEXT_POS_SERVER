from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse


router = Router(tags=["inventory"], auth=auth_bearer)


@router.get("/permissions-check", response=ApiResponse)
@permission_required("inventory_view")
def permissionsCheck(request):
    return successResponse(
        "Inventory permission check passed.",
        data={"module": "inventory", "required_permission": "inventory_view"},
    )
