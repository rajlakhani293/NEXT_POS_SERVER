# type: ignore
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema
from apps.registers.schemas import (
    CashRegisterIn,
    CashRegisterUpdateIn,
)
from apps.registers.services import RegisterService


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

