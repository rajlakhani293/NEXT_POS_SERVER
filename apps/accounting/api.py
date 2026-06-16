from typing import Optional
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.accounting.schemas import ManualTransactionIn, TransactionAccountIn, TransactionAccountUpdateIn, TransactionRuleIn, TransactionRuleUpdateIn
from apps.accounting.services import (
    AccountingService,
    TransactionAccountService,
    TransactionRuleService,
    TransactionService,
)
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema


router = Router(tags=["accounting"], auth=auth_bearer)


@router.post("/accounts/", response=ApiResponse)
@permission_required("settings_update")
def createAccount(request, payload: TransactionAccountIn):
    return TransactionAccountService.create(payload.dict(), request)


@router.post("/accounts/get-transactions", response=ApiResponse)
@permission_required("reports_view")
def getAllAccounts(request, payload: Optional[dict] = None):
    return TransactionAccountService.getAll(payload, request)


@router.get("/accounts/dropdown-list", response=ApiResponse)
@permission_required("reports_view")
def getAccountsDropdown(request):
    return TransactionAccountService.dropdownList(request)


@router.delete("/accounts/delete", response=ApiResponse)
@permission_required("settings_update")
def deleteAccounts(request, payload: BulkIdsSchema):
    return TransactionAccountService.delete(payload.dict(), request)


@router.patch("/accounts/status", response=ApiResponse)
@permission_required("settings_update")
def updateAccountStatus(request, payload: StatusUpdateSchema):
    return TransactionAccountService.updateStatus(payload.dict(), request)


@router.get("/accounts/{account_id}", response=ApiResponse)
@permission_required("reports_view")
def getAccountById(request, account_id: int):
    return TransactionAccountService.getById(account_id, request)


@router.put("/accounts/{account_id}", response=ApiResponse)
@permission_required("settings_update")
def updateAccount(request, account_id: int, payload: TransactionAccountUpdateIn):
    return TransactionAccountService.update(account_id, payload.dict(exclude_none=True), request)

@router.get("/rules/actions", response=ApiResponse)
@permission_required("reports_view")
def getAccountingActions(request):
    return TransactionRuleService.eventOptions()


@router.get("/rules", response=ApiResponse)
@permission_required("reports_view")
def getAccountingRules(request):
    return TransactionRuleService.getAll(request)


@router.post("/rules/", response=ApiResponse)
@permission_required("settings_update")
def createAccountingRule(request, payload: TransactionRuleIn):
    return TransactionRuleService.create(payload.dict(), request)


@router.put("/rules/{rule_id}", response=ApiResponse)
@permission_required("settings_update")
def updateAccountingRule(request, rule_id: int, payload: TransactionRuleUpdateIn):
    return TransactionRuleService.update(rule_id, payload.dict(exclude_none=True), request)


@router.delete("/rules/delete", response=ApiResponse)
@permission_required("settings_update")
def deleteAccountingRules(request, payload: BulkIdsSchema):
    return TransactionRuleService.delete(payload.dict(), request)


@router.post("/rules/reset", response=ApiResponse)
@permission_required("settings_update")
def resetAccountingRules(request):
    return TransactionRuleService.reset(request)


@router.post("/transactions/", response=ApiResponse)
@permission_required("settings_update")
def createManualTransaction(request, payload: ManualTransactionIn):
    return TransactionService.createManual(payload.dict(), request)


@router.post("/transactions/get-transactions", response=ApiResponse)
@permission_required("reports_view")
def getAllTransactions(request, payload: Optional[dict] = None):
    return TransactionService.getAll(payload, request)


@router.post("/history/get-transactions", response=ApiResponse)
@permission_required("reports_view")
def getTransactionHistory(request, payload: Optional[dict] = None):
    return TransactionService.history(payload, request)


@router.post("/bootstrap", response=ApiResponse)
@permission_required("settings_update")
def bootstrapAccounting(request):
    return AccountingService.bootstrapSystemAccounts(request)
