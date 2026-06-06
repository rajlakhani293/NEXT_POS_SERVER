# type: ignore
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode
from apps.common.responses import successResponse
from apps.expenses.models import ExpenseCategory, ExpenseEntry
from apps.payments.models import paymentTypeValues
from apps.registers.models import CashierShift, CashRegisterEntry


def money(value):
    return Decimal(str(value or 0))


class ExpenseCategoryService:
    @staticmethod
    def create(data, request):
        data["code"] = buildCode(ExpenseCategory, data.get("name"), data.get("code"), request)
        category = commonQuery.createRecord(ExpenseCategory, data, request=request, tenant_config=True)
        return successResponse("Expense category created successfully.", data=category)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            ExpenseCategory,
            data,
            [["name", True, True], ["code", True, True], ["description", True, True]],
            {"attributes": ["id", "name", "code", "description", "status"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Expense categories retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            ExpenseCategory,
            {},
            {"attributes": ["id", "name", "code"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getById(category_id, request):
        category = commonQuery.findOneRecord(ExpenseCategory, category_id, request=request, tenant_config=True)
        if category is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense category not found.")
        return successResponse("Expense category retrieved successfully.", data=category)

    @staticmethod
    def update(category_id, data, request):
        if data.get("code"):
            data["code"] = buildCode(
                ExpenseCategory,
                data.get("name") or "Expense Category",
                data.get("code"),
                request,
                exclude_id=category_id,
            )
        updated = commonQuery.updateRecordById(ExpenseCategory, category_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense category not found.")
        return successResponse("Expense category updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(ExpenseCategory, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense category not found.")
        return successResponse("Expense categories deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(ExpenseCategory, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense category not found.")
        return successResponse("Expense category status updated successfully.", data={"updated_count": count, "status": status})


class ExpenseEntryService:
    @staticmethod
    def validatePayload(data, request):
        category = commonQuery.findOneRecord(ExpenseCategory, data.get("category_id"), request=request, tenant_config=True)
        if category is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense category not found.")
        if money(data.get("amount")) <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Amount must be greater than 0.")
        if data.get("payment_type") and data.get("payment_type") not in paymentTypeValues():
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid payment type.")
        if data.get("shift_id"):
            shift = commonQuery.findOneRecord(CashierShift, data["shift_id"], request=request, tenant_config=True)
            if shift is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Cashier shift not found.")
        return category

    @staticmethod
    def create(data, request):
        with transaction.atomic():
            ExpenseEntryService.validatePayload(data, request)
            expense = commonQuery.createRecord(ExpenseEntry, data, request=request, tenant_config=True)
            if data.get("payment_type") == "cash" and data.get("shift_id"):
                amount = money(data.get("amount"))
                shift = commonQuery.findOneRecord(CashierShift, data["shift_id"], request=request, tenant_config=True)
                balance_before = money(shift.get("expected_cash"))
                balance_after = balance_before - amount
                CashierShift.objects.filter(id=shift["id"]).update(
                    expected_cash=F("expected_cash") - amount,
                    total_cash_out=F("total_cash_out") + amount,
                )
                commonQuery.createRecord(
                    CashRegisterEntry,
                    {
                        "shift_id": shift["id"],
                        "register_id": shift["register_id"],
                        "cashier_id": request.user.id,
                        "payment_type": "cash",
                        "entry_type": "expense",
                        "amount": amount,
                        "balance_before": balance_before,
                        "balance_after": balance_after,
                        "reference_type": "expense",
                        "reference_id": expense["id"],
                        "note": data.get("note") or "Expense",
                    },
                    request=request,
                    tenant_config=True,
                )
            return successResponse("Expense created successfully.", data=expense)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            ExpenseEntry,
            data,
            [["note", True, True], ["reference_number", True, True], ["payment_type", True, True]],
            {
                "attributes": [
                    "id",
                    "category_id",
                    "category__name",
                    "amount",
                    "expense_date",
                    "payment_type",
                    "shift_id",
                    "reference_number",
                    "note",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Expenses retrieved successfully.", data=result)

    @staticmethod
    def getById(expense_id, request):
        expense = commonQuery.findOneRecord(ExpenseEntry, expense_id, request=request, tenant_config=True)
        if expense is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense not found.")
        return successResponse("Expense retrieved successfully.", data=expense)

    @staticmethod
    def update(expense_id, data, request):
        if "amount" in data and money(data.get("amount")) <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Amount must be greater than 0.")
        if data.get("category_id"):
            ExpenseEntryService.validatePayload({"amount": 1, **data}, request)
        updated = commonQuery.updateRecordById(ExpenseEntry, expense_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense not found.")
        return successResponse("Expense updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(ExpenseEntry, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense not found.")
        return successResponse("Expenses deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(ExpenseEntry, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense not found.")
        return successResponse("Expense status updated successfully.", data={"updated_count": count, "status": status})
