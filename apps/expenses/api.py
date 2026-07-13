# type: ignore
from ninja import Router
from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData
from apps.expenses.schemas import (
    ExpenseCategoryIn,
    ExpenseCategoryUpdateIn,
    ExpenseIn,
    ExpenseUpdateIn,
)
from apps.expenses.services import ExpenseCategoryService, ExpenseService

router = Router(tags=["expenses"], auth=auth_bearer)


# ----------------- Expense Category Endpoints -----------------

@router.get("/categories/dropdown-list", response=ApiResponse)
@permissionRequired("expenses_view")
def getExpenseCategoriesDropdown(request):
    return ExpenseCategoryService.dropdownList(request)


@router.post("/categories/get-transactions", response=ApiResponse)
@permissionRequired("expenses_view")
def getExpenseCategoriesData(request, payload: dict = None):
    return ExpenseCategoryService.getAll(payload, request)


@router.post("/categories/", response=ApiResponse)
@permissionRequired("expenses_create")
def createExpenseCategory(request, payload: ExpenseCategoryIn):
    return ExpenseCategoryService.create(payloadData(payload), request)


@router.patch("/categories/status", response=ApiResponse)
@permissionRequired("expenses_update")
def updateExpenseCategoryStatus(request, payload: StatusUpdateSchema):
    return ExpenseCategoryService.updateStatus(payloadData(payload), request)


@router.put("/categories/{id}", response=ApiResponse)
@permissionRequired("expenses_update")
def editExpenseCategory(request, id: int, payload: ExpenseCategoryUpdateIn):
    return ExpenseCategoryService.edit(id, payloadData(payload), request)


@router.delete("/categories/delete", response=ApiResponse)
@permissionRequired("expenses_delete")
def deleteExpenseCategory(request, payload: BulkIdsSchema):
    return ExpenseCategoryService.delete(payloadData(payload), request)


@router.get("/categories/{id}", response=ApiResponse)
@permissionRequired("expenses_view")
def getExpenseCategoryById(request, id: int):
    return ExpenseCategoryService.getById(id, request)


# ----------------- Expense Endpoints -----------------

@router.post("/get-transactions", response=ApiResponse)
@permissionRequired("expenses_view")
def getExpensesData(request, payload: dict = None):
    return ExpenseService.getAll(payload, request)


@router.post("/", response=ApiResponse)
@permissionRequired("expenses_create")
def createExpense(request, payload: ExpenseIn):
    return ExpenseService.create(payloadData(payload), request)


@router.patch("/status", response=ApiResponse)
@permissionRequired("expenses_update")
def updateExpenseStatus(request, payload: StatusUpdateSchema):
    return ExpenseService.updateStatus(payloadData(payload), request)


@router.put("/{id}", response=ApiResponse)
@permissionRequired("expenses_update")
def editExpense(request, id: int, payload: ExpenseUpdateIn):
    return ExpenseService.edit(id, payloadData(payload), request)


@router.delete("/delete", response=ApiResponse)
@permissionRequired("expenses_delete")
def deleteExpense(request, payload: BulkIdsSchema):
    return ExpenseService.delete(payloadData(payload), request)


@router.get("/{id}", response=ApiResponse)
@permissionRequired("expenses_view")
def getExpenseById(request, id: int):
    return ExpenseService.getById(id, request)
