from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema
from apps.payments.services import PaymentTypeService
from apps.payments.schemas import (
    PaymentTypeCreateIn,
    PaymentTypeListIn,
    PaymentTypeUpdateIn,
)


router = Router(tags=["payments"], auth=auth_bearer)


@router.post("/types/", response=ApiResponse)
@permission_required("payments_create")
def createPaymentType(request, payload: PaymentTypeCreateIn):
    return PaymentTypeService.createPaymentType(payload.dict(), request)


@router.post("/types/get-transactions", response=ApiResponse)
@permission_required("payments_view")
def listPaymentTypes(request, payload: PaymentTypeListIn):
    data = PaymentTypeService.listPaymentTypes(payload.dict(), request)
    return successResponse("Payment types retrieved successfully.", data=data)


@router.get("/types/dropdown-list", response=ApiResponse)
@permission_required("payments_view")
def getPaymentTypeDropdown(request):
    return PaymentTypeService.dropdownList(request)


@router.patch("/types/status", response=ApiResponse)
@permission_required("payments_create")
def updatePaymentTypeStatus(request, payload: StatusUpdateSchema):
    data = PaymentTypeService.updatePaymentTypeStatus(payload.dict(), request)
    return successResponse("Payment type status updated successfully.", data=data)


@router.get("/types/{payment_type_id}", response=ApiResponse)
@permission_required("payments_view")
def getPaymentType(request, payment_type_id: int):
    data = PaymentTypeService.getPaymentType(payment_type_id, request)
    return successResponse("Payment type retrieved successfully.", data=data)


@router.put("/types/{payment_type_id}", response=ApiResponse)
@permission_required("payments_create")
def updatePaymentType(request, payment_type_id: int, payload: PaymentTypeUpdateIn):
    data = PaymentTypeService.updatePaymentType(payment_type_id, payload.dict(), request)
    return successResponse("Payment type updated successfully.", data=data)


@router.delete("/types/", response=ApiResponse)
@permission_required("payments_create")
def deletePaymentTypes(request, payload: BulkIdsSchema):
    data = PaymentTypeService.deletePaymentTypes(payload.dict(), request)
    return successResponse("Payment types deleted successfully.", data=data)
