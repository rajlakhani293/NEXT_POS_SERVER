from typing import Optional
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.customers.schemas import (
    CustomerGroupIn,
    CustomerGroupUpdateIn,
    CustomerIn,
    CustomerUpdateIn,
    DeleteSchema,
    StatusUpdateSchema,
)
from apps.customers.services import CustomerGroupService, CustomerService


router = Router(tags=["customers"], auth=auth_bearer)


@router.post("/", response=ApiResponse)
@permission_required("customers_create")
def createCustomer(request, payload: CustomerIn):
    return CustomerService.create(payload.dict(), request)


@router.post("/get-transactions", response=ApiResponse)
@permission_required("customers_view")
def getAllCustomers(request, payload: Optional[dict] = None):
    return CustomerService.getAll(payload, request)


@router.get("/dropdown-list", response=ApiResponse)
@permission_required("customers_view")
def getCustomerDropdown(request):
    return CustomerService.dropdownList(request)


@router.get("/groups/dropdown-list", response=ApiResponse)
@permission_required("customers_view")
def getCustomerGroupDropdown(request):
    return CustomerGroupService.dropdownList(request)


@router.post("/groups/", response=ApiResponse)
@permission_required("customers_create")
def createCustomerGroup(request, payload: CustomerGroupIn):
    return CustomerGroupService.create(payload.dict(), request)


@router.post("/groups/get-transactions", response=ApiResponse)
@permission_required("customers_view")
def getAllCustomerGroups(request, payload: Optional[dict] = None):
    return CustomerGroupService.getAll(payload, request)


@router.delete("/groups/delete", response=ApiResponse)
@permission_required("customers_delete")
def deleteCustomerGroups(request, payload: DeleteSchema):
    return CustomerGroupService.delete(payload.dict(), request)


@router.patch("/groups/status", response=ApiResponse)
@permission_required("customers_update")
def updateCustomerGroupStatus(request, payload: StatusUpdateSchema):
    return CustomerGroupService.updateStatus(payload.dict(), request)


@router.get("/groups/{group_id}", response=ApiResponse)
@permission_required("customers_view")
def getCustomerGroupById(request, group_id: int):
    return CustomerGroupService.getById(group_id, request)


@router.put("/groups/{group_id}", response=ApiResponse)
@permission_required("customers_update")
def updateCustomerGroup(request, group_id: int, payload: CustomerGroupUpdateIn):
    return CustomerGroupService.update(payload.dict(exclude_none=True), request, group_id)


@router.delete("/delete", response=ApiResponse)
@permission_required("customers_delete")
def deleteCustomers(request, payload: DeleteSchema):
    return CustomerService.delete(payload.dict(), request)


@router.patch("/status", response=ApiResponse)
@permission_required("customers_update")
def updateCustomerStatus(request, payload: StatusUpdateSchema):
    return CustomerService.updateStatus(payload.dict(), request)


@router.get("/{customer_id}", response=ApiResponse)
@permission_required("customers_view")
def getCustomerById(request, customer_id: int):
    return CustomerService.getById(customer_id, request)


@router.put("/{customer_id}", response=ApiResponse)
@permission_required("customers_update")
def updateCustomer(request, customer_id: int, payload: CustomerUpdateIn):
    return CustomerService.update(payload.dict(exclude_none=True), request, customer_id)
