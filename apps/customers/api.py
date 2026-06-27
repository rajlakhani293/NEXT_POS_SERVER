from typing import Optional
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData
from apps.customers.schemas import (
    CustomerAccountTransactionIn,
    CustomerGroupIn,
    CustomerGroupTransferIn,
    CustomerGroupUpdateIn,
    CustomerCreditIn,
    CustomerIn,
    CustomerSearchIn,
    CustomerUpdateIn,
)
from apps.customers.services import CustomerGroupService, CustomerService


router = Router(tags=["customers"], auth=auth_bearer)
groupsRouter = Router(tags=["customers-groups"], auth=auth_bearer)


@router.post("/", response=ApiResponse)
@permissionRequired("pos.create.customers")
def createCustomer(request, payload: CustomerIn):
    return CustomerService.create(payloadData(payload), request)


@router.post("/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.customers")
def getAllCustomers(request, payload: Optional[dict] = None):
    return CustomerService.getAll(payload, request)


@router.get("/dropdown-list", response=ApiResponse)
@permissionRequired("pos.read.customers")
def getCustomerDropdown(request):
    return CustomerService.dropdownList(request)


@router.get("/groups/dropdown-list", response=ApiResponse)
@permissionRequired("pos.read.customers-groups")
def getCustomerGroupDropdown(request):
    return CustomerGroupService.dropdownList(request)


@router.post("/groups/", response=ApiResponse)
@permissionRequired("pos.create.customers-groups")
def createCustomerGroup(request, payload: CustomerGroupIn):
    return CustomerGroupService.create(payloadData(payload), request)


@router.post("/groups/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.customers-groups")
def getAllCustomerGroups(request, payload: Optional[dict] = None):
    return CustomerGroupService.getAll(payload, request)


@router.delete("/groups/delete", response=ApiResponse)
@permissionRequired("pos.delete.customers-groups")
def deleteCustomerGroups(request, payload: BulkIdsSchema):
    return CustomerGroupService.delete(payloadData(payload), request)


@router.patch("/groups/status", response=ApiResponse)
@permissionRequired("pos.update.customers-groups")
def updateCustomerGroupStatus(request, payload: StatusUpdateSchema):
    return CustomerGroupService.updateStatus(payloadData(payload), request)


@router.post("/groups/transfer-customers", response=ApiResponse)
@permissionRequired("pos.update.customers-groups", "pos.update.customers", match="all")
def transferCustomerGroupCustomers(request, payload: CustomerGroupTransferIn):
    return CustomerGroupService.transferCustomers(payloadData(payload, by_alias=True), request)


@router.get("/groups/{group_id}", response=ApiResponse)
@permissionRequired("pos.read.customers-groups")
def getCustomerGroupById(request, group_id: int):
    return CustomerGroupService.getById(group_id, request)


@router.get("/groups/{group_id}/customers", response=ApiResponse)
@permissionRequired("pos.read.customers-groups", "pos.read.customers", match="all")
def getCustomerGroupCustomers(request, group_id: int):
    return CustomerGroupService.getCustomers(group_id, request)


@router.put("/groups/{group_id}", response=ApiResponse)
@permissionRequired("pos.update.customers-groups")
def updateCustomerGroup(request, group_id: int, payload: CustomerGroupUpdateIn):
    return CustomerGroupService.update(payloadData(payload, exclude_none=True), request, group_id)


@groupsRouter.post("/", response=ApiResponse)
@permissionRequired("pos.create.customers-groups")
def createCustomerGroupAtTopLevel(request, payload: CustomerGroupIn):
    return CustomerGroupService.create(payloadData(payload), request)


@groupsRouter.get("/{group_id}", response=ApiResponse)
@permissionRequired("pos.read.customers-groups")
def getCustomerGroupByIdAtTopLevel(request, group_id: int):
    return CustomerGroupService.getById(group_id, request)


@groupsRouter.get("/", response=ApiResponse)
@permissionRequired("pos.read.customers-groups")
def getCustomerGroupsAtTopLevel(request):
    return CustomerGroupService.getAll({}, request)


@groupsRouter.get("/{group_id}/customers", response=ApiResponse)
@permissionRequired("pos.read.customers-groups", "pos.read.customers", match="all")
def getCustomerGroupCustomersAtTopLevel(request, group_id: int):
    return CustomerGroupService.getCustomers(group_id, request)


@groupsRouter.delete("/{group_id}", response=ApiResponse)
@permissionRequired("pos.delete.customers-groups")
def deleteCustomerGroupAtTopLevel(request, group_id: int):
    return CustomerGroupService.delete({"ids": [group_id]}, request)


@groupsRouter.post("/transfer-customers", response=ApiResponse)
@permissionRequired("pos.update.customers-groups", "pos.update.customers", match="all")
def transferCustomerGroupCustomersAtTopLevel(request, payload: CustomerGroupTransferIn):
    return CustomerGroupService.transferCustomers(payloadData(payload, by_alias=True), request)


@groupsRouter.put("/{group_id}", response=ApiResponse)
@permissionRequired("pos.update.customers-groups")
def updateCustomerGroupAtTopLevel(request, group_id: int, payload: CustomerGroupUpdateIn):
    return CustomerGroupService.update(payloadData(payload, exclude_none=True), request, group_id)


@router.delete("/delete", response=ApiResponse)
@permissionRequired("pos.delete.customers")
def deleteCustomers(request, payload: BulkIdsSchema):
    return CustomerService.delete(payloadData(payload), request)


@router.patch("/status", response=ApiResponse)
@permissionRequired("pos.update.customers")
def updateCustomerStatus(request, payload: StatusUpdateSchema):
    return CustomerService.updateStatus(payloadData(payload), request)


@router.post("/search", response=ApiResponse)
@permissionRequired("pos.read.customers")
def searchCustomers(request, payload: CustomerSearchIn):
    return CustomerService.search(payloadData(payload), request)


@router.get("/recently-active", response=ApiResponse)
@permissionRequired("pos.read.customers")
def getRecentlyActiveCustomers(request, limit: int = 10):
    return CustomerService.recentlyActive(limit, request)


@router.delete("/using-email/{email}", response=ApiResponse)
@permissionRequired("pos.delete.customers")
def deleteCustomerUsingEmail(request, email: str):
    return CustomerService.deleteUsingEmail(email, request)


@router.get("/{customer_id}", response=ApiResponse)
@permissionRequired("pos.read.customers")
def getCustomerById(request, customer_id: int):
    return CustomerService.getById(customer_id, request)


@router.put("/{customer_id}", response=ApiResponse)
@permissionRequired("pos.update.customers")
def updateCustomer(request, customer_id: int, payload: CustomerUpdateIn):
    return CustomerService.update(payloadData(payload, exclude_none=True), request, customer_id)


@router.post("/{customer_id}/credit-adjustment", response=ApiResponse)
@permissionRequired("pos.customers.manage-account-history")
def adjustCustomerCredit(request, customer_id: int, payload: CustomerCreditIn):
    return CustomerService.adjustCredit(customer_id, payloadData(payload), request)


@router.post("/{customer_id}/credit-ledger", response=ApiResponse)
@permissionRequired("pos.read.customers")
def getCustomerCreditLedger(request, customer_id: int, payload: Optional[dict] = None):
    return CustomerService.creditLedger(customer_id, payload, request)


@router.post("/{customer_id}/account-history", response=ApiResponse)
@permissionRequired("pos.read.customers")
def getCustomerAccountHistory(request, customer_id: int, payload: Optional[dict] = None):
    return CustomerService.creditLedger(customer_id, payload, request)


@router.get("/{customer_id}/addresses", response=ApiResponse)
@permissionRequired("pos.read.customers")
def getCustomerAddresses(request, customer_id: int):
    return CustomerService.addresses(customer_id, request)


@router.get("/{customer_id}/group", response=ApiResponse)
@permissionRequired("pos.read.customers", "pos.read.customers-groups", match="all")
def getCustomerGroup(request, customer_id: int):
    return CustomerService.group(customer_id, request)


@router.get("/{customer_id}/coupons", response=ApiResponse)
@permissionRequired("pos.read.customers")
def getCustomerCoupons(request, customer_id: int):
    return CustomerService.coupons(customer_id, request)


@router.get("/{customer_id}/rewards", response=ApiResponse)
@permissionRequired("pos.read.customers")
def getCustomerRewards(request, customer_id: int):
    return CustomerService.rewards(customer_id, request)


@router.post("/{customer_id}/crud/account-history", response=ApiResponse)
@permissionRequired("pos.customers.manage-account-history")
def createCustomerAccountHistory(request, customer_id: int, payload: CustomerAccountTransactionIn):
    return CustomerService.accountTransaction(customer_id, payloadData(payload), request)


@router.post("/{customer_id}/orders", response=ApiResponse)
@permissionRequired("pos.read.customers", "pos.read.orders", match="all")
def getCustomerOrderHistory(request, customer_id: int, payload: Optional[dict] = None):
    return CustomerService.orderHistory(customer_id, payload, request)
