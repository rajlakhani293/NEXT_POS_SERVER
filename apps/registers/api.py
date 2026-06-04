# type: ignore
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.registers.schemas import CloseShiftIn, OpenShiftIn
from apps.registers.services import CashierShiftService, RegisterService


router = Router(tags=["registers"], auth=auth_bearer)


@router.get("/permissions-check", response=ApiResponse)
@permission_required("cash_register_view")
def permissionsCheck(request):
    return successResponse(
        "Register permission check passed.",
        data={"module": "registers", "required_permission": "cash_register_view"},
    )


@router.get("/dropdown-list", response=ApiResponse)
@permission_required("cash_register_view")
def getRegisterDropdown(request):
    return RegisterService.dropdownList(request)


@router.get("/shifts/current", response=ApiResponse)
@permission_required("cash_register_view")
def getCurrentShift(request):
    return CashierShiftService.current(request)


@router.post("/shifts/open", response=ApiResponse)
@permission_required("cash_register_open")
def openShift(request, payload: OpenShiftIn):
    return CashierShiftService.open(payload.dict(), request)


@router.post("/shifts/close", response=ApiResponse)
@permission_required("cash_register_close")
def closeShift(request, payload: CloseShiftIn):
    return CashierShiftService.close(payload.dict(), request)


@router.post("/shifts/get-transactions", response=ApiResponse)
@permission_required("cash_register_view")
def getAllShifts(request, payload: dict = None):
    return CashierShiftService.getAll(payload, request)
