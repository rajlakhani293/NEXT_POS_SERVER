from typing import Optional
from ninja import Body, Router
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
@permissionRequired("pos.create.transactions-account")
def createAccount(request, payload: TransactionAccountIn):
    return TransactionAccountService.create(payloadData(payload), request)


@router.post("/accounts/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.transactions-account")
def getAllAccounts(request, payload: Optional[dict] = None):
    return TransactionAccountService.getAll(payload, request)


@router.get("/accounts/dropdown-list", response=ApiResponse)
@permissionRequired("pos.read.transactions-account")
def getAccountsDropdown(request):
    return TransactionAccountService.dropdownList(request)


@router.delete("/accounts/delete", response=ApiResponse)
@permissionRequired("pos.delete.transactions-account")
def deleteAccounts(request, payload: BulkIdsSchema):
    return TransactionAccountService.delete(payloadData(payload), request)


@router.patch("/accounts/status", response=ApiResponse)
@permissionRequired("pos.update.transactions-account")
def updateAccountStatus(request, payload: StatusUpdateSchema):
    return TransactionAccountService.updateStatus(payloadData(payload), request)


@router.get("/accounts/{account_id}", response=ApiResponse)
@permissionRequired("pos.read.transactions-account")
def getAccountById(request, account_id: int):
    return TransactionAccountService.getById(account_id, request)


@router.put("/accounts/{account_id}", response=ApiResponse)
@permissionRequired("pos.update.transactions-account")
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


@router.delete("/rules/delete", response=ApiResponse)
@permissionRequired("settings_update")
def deleteAccountingRules(request, payload: BulkIdsSchema):
    return TransactionRuleService.delete(payloadData(payload), request)


@router.put("/rules/{rule_id}", response=ApiResponse)
@permissionRequired("settings_update")
def updateAccountingRule(request, rule_id: int, payload: TransactionRuleUpdateIn):
    return TransactionRuleService.update(rule_id, payloadData(payload, exclude_none=True), request)


@router.post("/transactions/", response=ApiResponse)
@permissionRequired("settings_update")
def createManualTransaction(request, payload: ManualTransactionIn):
    return TransactionService.createManual(payloadData(payload), request)


@router.post("/transactions/get-transactions", response=ApiResponse)
@permissionRequired("reports_view")
def getAllTransactions(request, payload: Optional[dict] = None):
    return TransactionService.getAll(payload, request)


@router.post("/history/get-transactions", response=ApiResponse)
@permissionRequired("pos.read.transactions-history")
def getTransactionHistory(request, payload: Optional[dict] = None):
    return TransactionService.history(payload, request)


@router.delete("/history/{history_id}", response=ApiResponse)
@permissionRequired("pos.delete.transactions-history")
def deleteAccountingHistory(request, history_id: int):
    return TransactionService.deleteHistory(history_id, request)


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
def createTransaction(request, payload: dict = Body(...)):
    return TransactionService.createSource(payloadData(payload), request)


@transactionsRouter.post("/rules", response=ApiResponse)
@permissionRequired("expenses_update")
def saveTransactionRule(request, payload: dict = Body(...)):
    data = payloadData(payload)
    rule = data.get("rule") or data
    rule_id = rule.get("id")
    if rule_id:
        return TransactionRuleService.update(rule_id, rule, request)
    return TransactionRuleService.create(rule, request)


@transactionsRouter.put("/{transaction_id}", response=ApiResponse)
@permissionRequired("expenses_update")
def updateTransaction(request, transaction_id: int, payload: dict = Body(...)):
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
@permissionRequired("pos.create.transactions-history")
def createTransactionReflection(request, history_id: int):
    return AccountingService.reflectTransactionFromRule(history_id, request)


@transactionsRouter.delete("/history/{history_id}", response=ApiResponse)
@permissionRequired("pos.delete.transactions-history")
def deleteTransactionHistory(request, history_id: int):
    return TransactionService.deleteHistory(history_id, request)


@transactionsRouter.get("/{transaction_id}", response=ApiResponse)
@permissionRequired("expenses_view")
def getTransaction(request, transaction_id: int):
    return TransactionService.getById(transaction_id, request)


@transactionAccountsRouter.get("/", response=ApiResponse)
@permissionRequired("pos.read.transactions-account")
def getTransactionAccounts(request):
    return TransactionAccountService.getAll({}, request)


@transactionAccountsRouter.get("/sub-accounts", response=ApiResponse)
@permissionRequired("pos.read.transactions-account")
def getTransactionSubAccounts(request):
    return TransactionAccountService.getSubAccounts(request)


@transactionAccountsRouter.get("/actions", response=ApiResponse)
@permissionRequired("pos.read.transactions-account")
def getTransactionActions(request):
    return TransactionRuleService.eventOptions()


@transactionAccountsRouter.post("/category-identifier", response=ApiResponse)
@permissionRequired("pos.read.transactions-account")
def getTransactionAccountsFromCategory(request, payload: dict = Body(...)):
    data = payloadData(payload)
    return TransactionAccountService.getFromCategory(data.get("identifier"), data.get("exclude"), request)


@transactionAccountsRouter.get("/reset-defaults", response=ApiResponse)
@permissionRequired("pos.update.transactions-account")
def resetDefaultTransactionAccounts(request):
    return TransactionAccountService.resetDefaults(request)


@transactionAccountsRouter.get("/{account_id}", response=ApiResponse)
@permissionRequired("pos.read.transactions-account")
def getTransactionAccount(request, account_id: int):
    return TransactionAccountService.getById(account_id, request)


@transactionAccountsRouter.get("/{account_id}/history", response=ApiResponse)
@permissionRequired("pos.read.transactions-account")
def getTransactionAccountHistory(request, account_id: int):
    return TransactionAccountService.getHistory(account_id, request)


@transactionAccountsRouter.post("/", response=ApiResponse)
@permissionRequired("pos.create.transactions-account")
def createTransactionAccount(request, payload: dict = Body(...)):
    return TransactionAccountService.create(payloadData(payload), request)


@transactionAccountsRouter.put("/{account_id}", response=ApiResponse)
@permissionRequired("pos.update.transactions-account")
def updateTransactionAccount(request, account_id: int, payload: dict = Body(...)):
    return TransactionAccountService.update(account_id, payloadData(payload, exclude_none=True), request)


@transactionAccountsRouter.delete("/{account_id}", response=ApiResponse)
@permissionRequired("pos.delete.transactions-account")
def deleteTransactionAccount(request, account_id: int):
    return TransactionAccountService.delete({"ids": [account_id]}, request)
