from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.sales.schemas import SaleCreateIn
from apps.sales.services import SaleService


router = Router(tags=["sales"], auth=auth_bearer)


@router.post("/", response=ApiResponse)
@permission_required("sales_create")
def createSale(request, payload: SaleCreateIn):
    return SaleService.create(payload.dict(), request)


@router.get("/permissions-check", response=ApiResponse)
@permission_required("sales_view")
def permissionsCheck(request):
    return successResponse(
        "Sales permission check passed.",
        data={"module": "sales", "required_permission": "sales_view"},
    )
