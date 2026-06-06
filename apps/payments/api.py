from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.payments.services import PaymentTypeService


router = Router(tags=["payments"], auth=auth_bearer)


@router.get("/types/dropdown-list", response=ApiResponse)
@permission_required("payments_view")
def getPaymentTypeDropdown(request):
    return PaymentTypeService.dropdownList()
