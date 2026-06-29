from typing import Optional
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.accounting.schemas import AccountingSettingsIn, ManualTransactionIn, TransactionAccountIn, TransactionAccountUpdateIn, TransactionRuleIn, TransactionRuleUpdateIn
from apps.accounting.services import (
    AccountingService,
    AccountingSettingsService,
    TransactionAccountService,
    TransactionRuleService,
    TransactionService,
)
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData


router = Router(tags=["accounting"], auth=auth_bearer)
transactionsRouter = Router(tags=["transactions"], auth=auth_bearer)
transactionAccountsRouter = Router(tags=["transaction-accounts"], auth=auth_bearer)


@router.post("/accounts/", response=ApiResponse)
@permissionRequired("settings_update")
def createAccount(request, payload: TransactionAccountIn):
    return TransactionAccountService.create(payloadData(payload), request)


@router.post("/accounts/get-transactions", response=ApiResponse)
@permissionRequired("reports_view")
def getAllAccounts(request, payload: Optional[dict] = None):
    return TransactionAccountService.getAll(payload, request)


@router.get("/accounts/dropdown-list", response=ApiResponse)
@permissionRequired("reports_view")
def getAccountsDropdown(request):
    return TransactionAccountService.dropdownList(request)


@router.delete("/accounts/delete", response=ApiResponse)
@permissionRequired("settings_update")
def deleteAccounts(request, payload: BulkIdsSchema):
    return TransactionAccountService.delete(payloadData(payload), request)


@router.patch("/accounts/status", response=ApiResponse)
@permissionRequired("settings_update")
def updateAccountStatus(request, payload: StatusUpdateSchema):
    return TransactionAccountService.updateStatus(payloadData(payload), request)


@router.get("/accounts/{account_id}", response=ApiResponse)
@permissionRequired("reports_view")
def getAccountById(request, account_id: int):
    return TransactionAccountService.getById(account_id, request)


@router.put("/accounts/{account_id}", response=ApiResponse)
@permissionRequired("settings_update")
def updateAccount(request, account_id: int, payload: TransactionAccountUpdateIn):
    return TransactionAccountService.update(account_id, payloadData(payload, exclude_none=True), request)

@router.get("/rules/actions", response=ApiResponse)
@permissionRequired("reports_view")
def getAccountingActions(request):
    return TransactionRuleService.eventOptions()


@router.get("/rules", response=ApiResponse)
@permissionRequired("reports_view")
def getAccountingRules(request):
    return TransactionRuleService.getAll(request)


@router.post("/rules/", response=ApiResponse)
@permissionRequired("settings_update")
def createAccountingRule(request, payload: TransactionRuleIn):
    return TransactionRuleService.create(payloadData(payload), request)


@router.put("/rules/{rule_id}", response=ApiResponse)
@permissionRequired("settings_update")
def updateAccountingRule(request, rule_id: int, payload: TransactionRuleUpdateIn):
    return TransactionRuleService.update(rule_id, payloadData(payload, exclude_none=True), request)


@router.delete("/rules/delete", response=ApiResponse)
@permissionRequired("settings_update")
def deleteAccountingRules(request, payload: BulkIdsSchema):
    return TransactionRuleService.delete(payloadData(payload), request)


@router.post("/rules/reset", response=ApiResponse)
@permissionRequired("settings_update")
def resetAccountingRules(request):
    return TransactionRuleService.reset(request)


@router.post("/transactions/", response=ApiResponse)
@permissionRequired("settings_update")
def createManualTransaction(request, payload: ManualTransactionIn):
    return TransactionService.createManual(payloadData(payload), request)


@router.post("/transactions/get-transactions", response=ApiResponse)
@permissionRequired("reports_view")
def getAllTransactions(request, payload: Optional[dict] = None):
    return TransactionService.getAll(payload, request)


@router.post("/history/get-transactions", response=ApiResponse)
@permissionRequired("reports_view")
def getTransactionHistory(request, payload: Optional[dict] = None):
    return TransactionService.history(payload, request)


@router.post("/balances/recompute", response=ApiResponse)
@permissionRequired("settings_update")
def recomputeAccountingBalances(request, payload: Optional[dict] = None):
    return TransactionService.enqueueBalanceRecompute(payload or {}, request)


@router.post("/bootstrap", response=ApiResponse)
@permissionRequired("settings_update")
def bootstrapAccounting(request):
    return AccountingService.bootstrapSystemAccounts(request)


@router.get("/settings", response=ApiResponse)
@permissionRequired("reports_view")
def getAccountingSettings(request):
    return AccountingSettingsService.get(request)


@router.put("/settings", response=ApiResponse)
@permissionRequired("settings_update")
def updateAccountingSettings(request, payload: AccountingSettingsIn):
    return AccountingSettingsService.update(payloadData(payload, exclude_none=True), request)


@transactionsRouter.get("/", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransactions(request):
    return TransactionService.getAll({}, request)


@transactionsRouter.get("/configurations", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransactionConfigurations(request):
    return TransactionService.configurations(None, request)


@transactionsRouter.get("/configurations/{transaction_id}", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransactionConfigurationsById(request, transaction_id: int):
    return TransactionService.configurations(transaction_id, request)


@transactionsRouter.get("/rules", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransactionRules(request):
    return TransactionRuleService.getAll(request)


@transactionsRouter.get("/trigger", response=ApiResponse)
@permissionRequired("expenses_update")
def triggerPendingTransactions(request):
    return TransactionService.triggerTransaction(None, request)


@transactionsRouter.post("/", response=ApiResponse)
@permissionRequired("expenses_create")
def createTransaction(request, payload: dict):
    return TransactionService.createSource(payloadData(payload), request)


@transactionsRouter.post("/rules", response=ApiResponse)
@permissionRequired("expenses_update")
def saveTransactionRule(request, payload: dict):
    data = payloadData(payload)
    rule = data.get("rule") or data
    rule_id = rule.get("id")
    if rule_id:
        return TransactionRuleService.update(rule_id, rule, request)
    return TransactionRuleService.create(rule, request)


@transactionsRouter.put("/{transaction_id}", response=ApiResponse)
@permissionRequired("expenses_update")
def updateTransaction(request, transaction_id: int, payload: dict):
    return TransactionService.updateSource(transaction_id, payloadData(payload, exclude_none=True), request)


@transactionsRouter.delete("/{transaction_id}", response=ApiResponse)
@permissionRequired("expenses_delete")
def deleteTransaction(request, transaction_id: int):
    return TransactionService.deleteSource(transaction_id, request)


@transactionsRouter.get("/trigger/{transaction_id}", response=ApiResponse)
@permissionRequired("expenses_update")
def triggerTransaction(request, transaction_id: int):
    return TransactionService.triggerTransaction(transaction_id, request)


@transactionsRouter.get("/history/{history_id}/create-reflection", response=ApiResponse)
@permissionRequired("expenses_create")
def createTransactionReflection(request, history_id: int):
    return AccountingService.reflectTransactionFromRule(history_id, request)


@transactionsRouter.get("/{transaction_id}", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransaction(request, transaction_id: int):
    return TransactionService.getById(transaction_id, request)


@transactionAccountsRouter.get("/", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransactionAccounts(request):
    return TransactionAccountService.getAll({}, request)


@transactionAccountsRouter.get("/sub-accounts", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransactionSubAccounts(request):
    return TransactionAccountService.getSubAccounts(request)


@transactionAccountsRouter.get("/actions", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransactionActions(request):
    return TransactionRuleService.eventOptions()


@transactionAccountsRouter.post("/category-identifier", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransactionAccountsFromCategory(request, payload: dict):
    data = payloadData(payload)
    return TransactionAccountService.getFromCategory(data.get("identifier"), data.get("exclude"), request)


@transactionAccountsRouter.get("/reset-defaults", response=ApiResponse)
@permissionRequired("expenses_update")
def resetDefaultTransactionAccounts(request):
    return TransactionAccountService.resetDefaults(request)


@transactionAccountsRouter.get("/{account_id}", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransactionAccount(request, account_id: int):
    return TransactionAccountService.getById(account_id, request)


@transactionAccountsRouter.get("/{account_id}/history", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransactionAccountHistory(request, account_id: int):
    return TransactionAccountService.getHistory(account_id, request)


@transactionAccountsRouter.post("/", response=ApiResponse)
@permissionRequired("expenses_create")
def createTransactionAccount(request, payload: dict):
    return TransactionAccountService.create(payloadData(payload), request)


@transactionAccountsRouter.put("/{account_id}", response=ApiResponse)
@permissionRequired("expenses_update")
def updateTransactionAccount(request, account_id: int, payload: dict):
    return TransactionAccountService.update(account_id, payloadData(payload, exclude_none=True), request)


@transactionAccountsRouter.delete("/{account_id}", response=ApiResponse)
@permissionRequired("expenses_delete")
def deleteTransactionAccount(request, account_id: int):
    return TransactionAccountService.delete({"ids": [account_id]}, request)
