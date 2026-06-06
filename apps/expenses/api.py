from typing import Optional

from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.expenses.schemas import (
    DeleteSchema,
    ExpenseCategoryIn,
    ExpenseCategoryUpdateIn,
    ExpenseEntryIn,
    ExpenseEntryUpdateIn,
    StatusUpdateSchema,
)
from apps.expenses.services import ExpenseCategoryService, ExpenseEntryService


router = Router(tags=["expenses"], auth=auth_bearer)


@router.post("/categories/", response=ApiResponse)
@permission_required("expenses_create")
def createExpenseCategory(request, payload: ExpenseCategoryIn):
    return ExpenseCategoryService.create(payload.dict(), request)


@router.post("/categories/get-transactions", response=ApiResponse)
@permission_required("expenses_view")
def getAllExpenseCategories(request, payload: Optional[dict] = None):
    return ExpenseCategoryService.getAll(payload, request)


@router.get("/categories/dropdown-list", response=ApiResponse)
@permission_required("expenses_view")
def getExpenseCategoryDropdown(request):
    return ExpenseCategoryService.dropdownList(request)


@router.delete("/categories/delete", response=ApiResponse)
@permission_required("expenses_update")
def deleteExpenseCategories(request, payload: DeleteSchema):
    return ExpenseCategoryService.delete(payload.dict(), request)


@router.patch("/categories/status", response=ApiResponse)
@permission_required("expenses_update")
def updateExpenseCategoryStatus(request, payload: StatusUpdateSchema):
    return ExpenseCategoryService.updateStatus(payload.dict(), request)


@router.get("/categories/{category_id}", response=ApiResponse)
@permission_required("expenses_view")
def getExpenseCategoryById(request, category_id: int):
    return ExpenseCategoryService.getById(category_id, request)


@router.put("/categories/{category_id}", response=ApiResponse)
@permission_required("expenses_update")
def updateExpenseCategory(request, category_id: int, payload: ExpenseCategoryUpdateIn):
    return ExpenseCategoryService.update(category_id, payload.dict(exclude_none=True), request)


@router.post("/", response=ApiResponse)
@permission_required("expenses_create")
def createExpense(request, payload: ExpenseEntryIn):
    return ExpenseEntryService.create(payload.dict(), request)


@router.post("/get-transactions", response=ApiResponse)
@permission_required("expenses_view")
def getAllExpenses(request, payload: Optional[dict] = None):
    return ExpenseEntryService.getAll(payload, request)


@router.delete("/delete", response=ApiResponse)
@permission_required("expenses_update")
def deleteExpenses(request, payload: DeleteSchema):
    return ExpenseEntryService.delete(payload.dict(), request)


@router.patch("/status", response=ApiResponse)
@permission_required("expenses_update")
def updateExpenseStatus(request, payload: StatusUpdateSchema):
    return ExpenseEntryService.updateStatus(payload.dict(), request)


@router.get("/{expense_id}", response=ApiResponse)
@permission_required("expenses_view")
def getExpenseById(request, expense_id: int):
    return ExpenseEntryService.getById(expense_id, request)


@router.put("/{expense_id}", response=ApiResponse)
@permission_required("expenses_update")
def updateExpense(request, expense_id: int, payload: ExpenseEntryUpdateIn):
    return ExpenseEntryService.update(expense_id, payload.dict(exclude_none=True), request)
