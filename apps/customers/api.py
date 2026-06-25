from typing import Optional
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData
from apps.customers.schemas import (
    CustomerGroupIn,
    CustomerGroupUpdateIn,
    CustomerCreditIn,
    CustomerIn,
    CustomerUpdateIn,
)
from apps.customers.services import CustomerGroupService, CustomerService


router = Router(tags=["customers"], auth=auth_bearer)


@router.post("/", response=ApiResponse)
@permissionRequired("customers_create")
def createCustomer(request, payload: CustomerIn):
    return CustomerService.create(payloadData(payload), request)


@router.post("/get-transactions", response=ApiResponse)
@permissionRequired("customers_view")
def getAllCustomers(request, payload: Optional[dict] = None):
    return CustomerService.getAll(payload, request)


@router.get("/dropdown-list", response=ApiResponse)
@permissionRequired("customers_view")
def getCustomerDropdown(request):
    return CustomerService.dropdownList(request)


@router.get("/groups/dropdown-list", response=ApiResponse)
@permissionRequired("customers_view")
def getCustomerGroupDropdown(request):
    return CustomerGroupService.dropdownList(request)


@router.post("/groups/", response=ApiResponse)
@permissionRequired("customers_create")
def createCustomerGroup(request, payload: CustomerGroupIn):
    return CustomerGroupService.create(payloadData(payload), request)


@router.post("/groups/get-transactions", response=ApiResponse)
@permissionRequired("customers_view")
def getAllCustomerGroups(request, payload: Optional[dict] = None):
    return CustomerGroupService.getAll(payload, request)


@router.delete("/groups/delete", response=ApiResponse)
@permissionRequired("customers_delete")
def deleteCustomerGroups(request, payload: BulkIdsSchema):
    return CustomerGroupService.delete(payloadData(payload), request)


@router.patch("/groups/status", response=ApiResponse)
@permissionRequired("customers_update")
def updateCustomerGroupStatus(request, payload: StatusUpdateSchema):
    return CustomerGroupService.updateStatus(payloadData(payload), request)


@router.get("/groups/{group_id}", response=ApiResponse)
@permissionRequired("customers_view")
def getCustomerGroupById(request, group_id: int):
    return CustomerGroupService.getById(group_id, request)


@router.put("/groups/{group_id}", response=ApiResponse)
@permissionRequired("customers_update")
def updateCustomerGroup(request, group_id: int, payload: CustomerGroupUpdateIn):
    return CustomerGroupService.update(payloadData(payload, exclude_none=True), request, group_id)


@router.delete("/delete", response=ApiResponse)
@permissionRequired("customers_delete")
def deleteCustomers(request, payload: BulkIdsSchema):
    return CustomerService.delete(payloadData(payload), request)


@router.patch("/status", response=ApiResponse)
@permissionRequired("customers_update")
def updateCustomerStatus(request, payload: StatusUpdateSchema):
    return CustomerService.updateStatus(payloadData(payload), request)


@router.get("/{customer_id}", response=ApiResponse)
@permissionRequired("customers_view")
def getCustomerById(request, customer_id: int):
    return CustomerService.getById(customer_id, request)


@router.put("/{customer_id}", response=ApiResponse)
@permissionRequired("customers_update")
def updateCustomer(request, customer_id: int, payload: CustomerUpdateIn):
    return CustomerService.update(payloadData(payload, exclude_none=True), request, customer_id)


@router.post("/{customer_id}/credit-adjustment", response=ApiResponse)
@permissionRequired("customers_update")
def adjustCustomerCredit(request, customer_id: int, payload: CustomerCreditIn):
    return CustomerService.adjustCredit(customer_id, payloadData(payload), request)


@router.post("/{customer_id}/credit-ledger", response=ApiResponse)
@permissionRequired("customers_view")
def getCustomerCreditLedger(request, customer_id: int, payload: Optional[dict] = None):
    return CustomerService.creditLedger(customer_id, payload, request)


@router.post("/{customer_id}/orders", response=ApiResponse)
@permissionRequired("customers_view")
def getCustomerOrderHistory(request, customer_id: int, payload: Optional[dict] = None):
    return CustomerService.orderHistory(customer_id, payload, request)

