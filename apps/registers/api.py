# type: ignore
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData
from apps.registers.schemas import (
    CashRegisterIn,
    CashRegisterUpdateIn,
    RegisterMoneyActionIn,
    RegisterStatusIn,
    ShiftOpenIn,
    ShiftCloseIn,
    ShiftMoneyActionIn,
)
from apps.registers.services import RegisterService


router = Router(tags=["registers"], auth=auth_bearer)


@router.get("/permissions-check", response=ApiResponse)
@permissionRequired("cash_register_view")
def permissionsCheck(request):
    return successResponse(
        "Register permission check passed.",
        data={"module": "registers", "required_permission": "cash_register_view"},
    )


@router.get("/dropdown-list", response=ApiResponse)
@permissionRequired("cash_register_view")
def getRegisterDropdown(request):
    return RegisterService.dropdownList(request)


@router.get("/", response=ApiResponse)
@permissionRequired("cash_register_view")
def getRegisters(request):
    return RegisterService.getRegisters(request)


@router.post("/", response=ApiResponse)
@permissionRequired("cash_register_open")
def createRegister(request, payload: CashRegisterIn):
    return RegisterService.create(payloadData(payload), request)


@router.post("/get-transactions", response=ApiResponse)
@permissionRequired("cash_register_view")
def getAllRegisters(request, payload: dict = None):
    return RegisterService.getAll(payload, request)


@router.delete("/delete", response=ApiResponse)
@permissionRequired("cash_register_close")
def deleteRegisters(request, payload: BulkIdsSchema):
    return RegisterService.delete(payloadData(payload), request)


@router.patch("/status", response=ApiResponse)
@permissionRequired("cash_register_close")
def updateRegisterStatus(request, payload: StatusUpdateSchema):
    return RegisterService.updateStatus(payloadData(payload), request)


@router.post("/open", response=ApiResponse)
@permissionRequired("cash_register_open")
def openRegister(request, payload: RegisterStatusIn):
    return RegisterService.openRegister(payloadData(payload), request)


@router.post("/close", response=ApiResponse)
@permissionRequired("cash_register_close")
def closeRegister(request, payload: RegisterStatusIn):
    return RegisterService.closeRegister(payloadData(payload), request)


@router.post("/cash-in", response=ApiResponse)
@permissionRequired("cash_register_open")
def cashIn(request, payload: RegisterMoneyActionIn):
    return RegisterService.cashIn(payloadData(payload), request)


@router.post("/cash-out", response=ApiResponse)
@permissionRequired("cash_register_close")
def cashOut(request, payload: RegisterMoneyActionIn):
    return RegisterService.cashOut(payloadData(payload), request)


@router.get("/shifts/current", response=ApiResponse)
@permissionRequired("cash_register_view")
def getCurrentShift(request):
    return RegisterService.getCurrentShift(request)


@router.post("/shifts/open", response=ApiResponse)
@permissionRequired("cash_register_open")
def openShift(request, payload: ShiftOpenIn):
    return RegisterService.openRegister({
        "register_id": payload.register_id,
        "amount": payload.amount,
        "note": payload.note or "Register opening",
    }, request)


@router.post("/shifts/close", response=ApiResponse)
@permissionRequired("cash_register_close")
def closeShift(request, payload: ShiftCloseIn):
    return RegisterService.closeRegister({
        "register_id": payload.shift_id,
        "amount": payload.declared_cash,
        "note": payload.note or "Register closing",
    }, request)


@router.post("/shifts/cash-in", response=ApiResponse)
@permissionRequired("cash_register_open")
def cashInShift(request, payload: ShiftMoneyActionIn):
    return RegisterService.cashIn({
        "register_id": payload.shift_id,
        "amount": payload.amount,
        "note": payload.note or "Cash in",
    }, request)


@router.post("/shifts/cash-out", response=ApiResponse)
@permissionRequired("cash_register_close")
def cashOutShift(request, payload: ShiftMoneyActionIn):
    return RegisterService.cashOut({
        "register_id": payload.shift_id,
        "amount": payload.amount,
        "note": payload.note or "Cash out",
    }, request)


@router.post("/shifts/get-transactions", response=ApiResponse)
@permissionRequired("cash_register_view")
def getShiftsData(request, payload: dict = None):
    return RegisterService.getShiftsData(payload, request)


@router.get("/shifts/{shift_id}", response=ApiResponse)
@permissionRequired("cash_register_view")
def getShiftById(request, shift_id: int):
    return RegisterService.getShiftById(shift_id, request)


@router.get("/{register_id}/session-history", response=ApiResponse)
@permissionRequired("cash_register_view")
def getRegisterSessionHistory(request, register_id: int):
    return RegisterService.getSessionHistory(register_id, request)


@router.get("/{register_id}", response=ApiResponse)
@permissionRequired("cash_register_view")
def getRegisterById(request, register_id: int):
    return RegisterService.getById(register_id, request)


@router.put("/{register_id}", response=ApiResponse)
@permissionRequired("cash_register_close")
def updateRegister(request, register_id: int, payload: CashRegisterUpdateIn):
    return RegisterService.update(register_id, payloadData(payload, exclude_none=True), request)
