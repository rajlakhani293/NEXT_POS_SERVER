# type: ignore
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from apps.accounting.models import ActiveTransactionHistory, Transaction, TransactionHistory
from apps.accounting.services import AccountingService
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode
from apps.common.responses import successResponse
from apps.expenses.models import ExpenseCategory, ExpenseEntry
from apps.notifications.services import NotificationService
from apps.payments.services import PaymentTypeService
from apps.registers.models import CashierShift, CashRegisterEntry


def money(value):
    return Decimal(str(value or 0))


class ExpenseCategoryService:
    DEFAULT_CATEGORIES = [
        {
            "name": "Direct Expenses",
            "code": "direct-expenses",
            "description": "Default direct expense category.",
        },
        {
            "name": "Operating Expenses",
            "code": "operating-expenses",
            "description": "Default operating expense category.",
        },
        {
            "name": "Rent Expenses",
            "code": "rent-expenses",
            "description": "Default rent expense category.",
        },
        {
            "name": "Other Expenses",
            "code": "other-expenses",
            "description": "Default other expense category.",
        },
    ]

    @staticmethod
    def ensureDefaultCategories(company, branch):
        seeded = []
        for item in ExpenseCategoryService.DEFAULT_CATEGORIES:
            category, _created = ExpenseCategory.objects.get_or_create(
                company_id=company.id,
                branch_id=branch.id,
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "description": item["description"],
                },
            )
            seeded.append(category)
        return seeded

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
    def getExpense(expense_id, request):
        expense = commonQuery.findOneRecord(ExpenseEntry, expense_id, request=request, tenant_config=True)
        if expense is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense not found.")
        return expense

    @staticmethod
    def getShift(shift_id, request, required=True):
        if not shift_id:
            if required:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Cashier shift not found.")
            return None
        shift = commonQuery.findOneRecord(CashierShift, shift_id, request=request, tenant_config=True)
        if shift is None and required:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cashier shift not found.")
        return shift

    @staticmethod
    def assertShiftEditable(shift):
        if shift and shift.get("shift_status") != "open":
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Cannot modify expense linked to a closed shift.")

    @staticmethod
    def validatePayload(data, request):
        category = commonQuery.findOneRecord(ExpenseCategory, data.get("category_id"), request=request, tenant_config=True)
        if category is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense category not found.")
        if money(data.get("amount")) <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Amount must be greater than 0.")
        if data.get("payment_type"):
            data["payment_type"] = PaymentTypeService.resolvePaymentType(
                data.get("payment_type"),
                request,
            )
        if data.get("shift_id"):
            ExpenseEntryService.getShift(data["shift_id"], request)
        return category

    @staticmethod
    def applyEffects(expense, request):
        if expense.get("payment_type") == "cash-payment" and expense.get("shift_id"):
            amount = money(expense.get("amount"))
            shift = ExpenseEntryService.getShift(expense["shift_id"], request)
            ExpenseEntryService.assertShiftEditable(shift)
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
                    "payment_type": "cash-payment",
                    "entry_type": "expense",
                    "amount": amount,
                    "balance_before": balance_before,
                    "balance_after": balance_after,
                    "reference_type": "expense",
                    "reference_id": expense["id"],
                    "note": expense.get("note") or "Expense",
                },
                request=request,
                tenant_config=True,
            )

        AccountingService.record(
            account_code="expense",
            name="Expense",
            transaction_type="expense",
            action_type="debit",
            amount=expense.get("amount"),
            source_type="expense",
            source_id=expense["id"],
            transaction_date=expense.get("expense_date"),
            description=expense.get("note") or "Expense",
            reference_number=expense.get("reference_number") or "",
            request=request,
        )

    @staticmethod
    def reverseEffects(expense, request):
        register_entries = list(
            CashRegisterEntry.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                reference_type="expense",
                reference_id=expense["id"],
                status__in=[0, 1],
            )
        )
        for entry in register_entries:
            shift = ExpenseEntryService.getShift(entry.shift_id, request)
            ExpenseEntryService.assertShiftEditable(shift)
            CashierShift.objects.filter(id=entry.shift_id).update(
                expected_cash=F("expected_cash") + entry.amount,
                total_cash_out=F("total_cash_out") - entry.amount,
            )
            entry.delete()

        histories = list(
            TransactionHistory.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                source_type="expense",
                source_id=expense["id"],
            ).select_related("account", "transaction")
        )
        for history in histories:
            reverse_action = "credit" if history.action_type == "debit" else "debit"
            AccountingService.updateBalances(
                history.account_id,
                history.amount,
                reverse_action,
                history.transaction.transaction_date,
                request,
            )
            ActiveTransactionHistory.objects.filter(transaction_history_id=history.id).delete()
            transaction_id = history.transaction_id
            history.delete()
            Transaction.objects.filter(id=transaction_id).delete()

    @staticmethod
    def create(data, request):
        with transaction.atomic():
            ExpenseEntryService.validatePayload(data, request)
            expense = commonQuery.createRecord(ExpenseEntry, data, request=request, tenant_config=True)
            ExpenseEntryService.applyEffects(expense, request)
            NotificationService.push(
                title="Expense recorded",
                message=f"Expense of {data.get('amount')} recorded.",
                notification_type="info",
                source_type="accounting",
                source_id=expense["id"],
                action_url="/expenses",
                request=request,
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
                    "shift__register__name",
                    "shift__shift_status",
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
        expense = ExpenseEntryService.getExpense(expense_id, request)
        return successResponse("Expense retrieved successfully.", data=expense)

    @staticmethod
    def update(expense_id, data, request):
        with transaction.atomic():
            expense = ExpenseEntryService.getExpense(expense_id, request)
            original_shift = ExpenseEntryService.getShift(expense.get("shift_id"), request, required=False)
            ExpenseEntryService.assertShiftEditable(original_shift)

            merged = {**expense, **data}
            if merged.get("amount") is not None and money(merged.get("amount")) <= 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Amount must be greater than 0.")
            ExpenseEntryService.validatePayload(
                {
                    "category_id": merged.get("category_id"),
                    "amount": merged.get("amount"),
                    "payment_type": merged.get("payment_type"),
                    "shift_id": merged.get("shift_id"),
                },
                request,
            )

            ExpenseEntryService.reverseEffects(expense, request)
            updated = commonQuery.updateRecordById(ExpenseEntry, expense_id, data, request=request, tenant_config=True)
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Expense not found.")
            ExpenseEntryService.applyEffects(updated, request)
            return successResponse("Expense updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        ids = data.get("ids")
        expense_ids = ids if isinstance(ids, list) else [ids]
        expenses = [
            ExpenseEntryService.getExpense(expense_id, request)
            for expense_id in expense_ids
        ]
        with transaction.atomic():
            for expense in expenses:
                shift = ExpenseEntryService.getShift(expense.get("shift_id"), request, required=False)
                ExpenseEntryService.assertShiftEditable(shift)
                ExpenseEntryService.reverseEffects(expense, request)
            count = commonQuery.softDeleteById(ExpenseEntry, ids, request=request, tenant_config=True)
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
