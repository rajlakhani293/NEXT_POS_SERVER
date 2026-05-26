from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse


router = Router(tags=["registers"], auth=auth_bearer)


@router.get("/permissions-check", response=ApiResponse)
@permission_required("cash_register_view")
def permissionsCheck(request):
    return successResponse(
        "Register permission check passed.",
        data={"module": "registers", "required_permission": "cash_register_view"},
    )
