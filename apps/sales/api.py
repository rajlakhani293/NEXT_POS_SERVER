from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, success_response


router = Router(tags=["sales"], auth=auth_bearer)


@router.get("/permissions-check", response=ApiResponse)
@permission_required("sales_view")
def permissionsCheck(request):
    return success_response(
        "Sales permission check passed.",
        data={"module": "sales", "required_permission": "sales_view"},
    )
