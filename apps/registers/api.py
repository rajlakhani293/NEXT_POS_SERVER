# type: ignore
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema
from apps.registers.schemas import (
    CashMovementIn,
    CashRegisterIn,
    CashRegisterUpdateIn,
    CloseShiftIn,
    OpenShiftIn,
)
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


@router.post("/", response=ApiResponse)
@permission_required("cash_register_open")
def createRegister(request, payload: CashRegisterIn):
    return RegisterService.create(payload.dict(), request)


@router.post("/get-transactions", response=ApiResponse)
@permission_required("cash_register_view")
def getAllRegisters(request, payload: dict = None):
    return RegisterService.getAll(payload, request)


@router.delete("/delete", response=ApiResponse)
@permission_required("cash_register_close")
def deleteRegisters(request, payload: BulkIdsSchema):
    return RegisterService.delete(payload.dict(), request)


@router.patch("/status", response=ApiResponse)
@permission_required("cash_register_close")
def updateRegisterStatus(request, payload: StatusUpdateSchema):
    return RegisterService.updateStatus(payload.dict(), request)


@router.get("/{register_id}", response=ApiResponse)
@permission_required("cash_register_view")
def getRegisterById(request, register_id: int):
    return RegisterService.getById(register_id, request)


@router.put("/{register_id}", response=ApiResponse)
@permission_required("cash_register_close")
def updateRegister(request, register_id: int, payload: CashRegisterUpdateIn):
    return RegisterService.update(register_id, payload.dict(exclude_none=True), request)


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


@router.get("/shifts/{shift_id}", response=ApiResponse)
@permission_required("cash_register_view")
def getShiftById(request, shift_id: int):
    return CashierShiftService.getById(shift_id, request)


@router.post("/shifts/{shift_id}/entries/get-transactions", response=ApiResponse)
@permission_required("cash_register_view")
def getShiftEntries(request, shift_id: int, payload: dict = None):
    return CashierShiftService.getEntries(shift_id, payload, request)


@router.get("/shifts/{shift_id}/z-report", response=ApiResponse)
@permission_required("cash_register_view")
def getShiftZReport(request, shift_id: int):
    return CashierShiftService.getZReport(shift_id, request)


@router.get("/shifts/{shift_id}/refresh", response=ApiResponse)
@permission_required("cash_register_view")
def refreshShift(request, shift_id: int):
    return CashierShiftService.refresh(shift_id, request)


@router.post("/shifts/cash-in", response=ApiResponse)
@permission_required("cash_register_cash_in")
def cashIn(request, payload: CashMovementIn):
    return CashierShiftService.cashMovement(payload.dict(), request, "cash_in")


@router.post("/shifts/cash-out", response=ApiResponse)
@permission_required("cash_register_cash_out")
def cashOut(request, payload: CashMovementIn):
    return CashierShiftService.cashMovement(payload.dict(), request, "cash_out")
