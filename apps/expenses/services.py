# type:ignore
from django.db import transaction
from django.db.models import F
from apps.accounting.models import (
    Transaction,
    TransactionAccount,
    TransactionHistory,
)
from apps.accounting.services import ACCOUNT_CODES, AccountingService
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode, decimalValue as money, validateTenantRelationId
from apps.common.responses import successResponse
from apps.expenses.models import ExpenseCategory, ExpenseEntry
from apps.notifications.services import NotificationService
from apps.payments.services import PaymentTypeService
from apps.registers.models import CashierShift, CashRegisterEntry


class ExpenseCategoryService:
    DEFAULT_CATEGORIES = [
        {
            "name": "Direct Expenses",
            "code": "direct-expenses",
            "account_code": ACCOUNT_CODES["direct_expenses"],
            "description": "Default direct expense category.",
        },
        {
            "name": "Operating Expenses",
            "code": "operating-expenses",
            "account_code": ACCOUNT_CODES["operating_expenses"],
            "description": "Default operating expense category.",
        },
        {
            "name": "Rent Expenses",
            "code": "rent-expenses",
            "account_code": ACCOUNT_CODES["rent_expenses"],
            "description": "Default rent expense category.",
        },
        {
            "name": "Other Expenses",
            "code": "other-expenses",
            "account_code": ACCOUNT_CODES["other_expenses"],
            "description": "Default other expense category.",
        },
    ]

    @staticmethod
    def ensureDefaultCategories(company, branch):
        seeded = []
        for item in ExpenseCategoryService.DEFAULT_CATEGORIES:
            account = TransactionAccount.objects.filter(
                company_id=company.id,
                branch_id=branch.id,
                account=item["account_code"],
            ).first()
            category, _created = ExpenseCategory.objects.get_or_create(
                company_id=company.id,
                branch_id=branch.id,
                code=item["code"],
                defaults={
                    "name": item["name"],
                    "description": item["description"],
                    "account": account,
                },
            )
            if account and category.account_id != account.id:
                category.account = account
                category.save(update_fields=["account", "updated_at"])
            seeded.append(category)
        return seeded

    @staticmethod
    def create(data, request):
        if data.get("account_id"):
            validateTenantRelationId(
                TransactionAccount,
                data["account_id"],
                request=request,
                label="Transaction account",
            )
        data["code"] = buildCode(ExpenseCategory, data.get("name"), data.get("code"), request)
        category = commonQuery.createRecord(ExpenseCategory, data, request=request, tenant_config=True)
        return successResponse("Expense category created successfully.", data=category)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            ExpenseCategory,
            data,
            [["name", True, True], ["code", True, True], ["description", True, True]],
            {"attributes": ["id", "name", "code", "account_id", "account__name", "description", "status"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Expense categories retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            ExpenseCategory,
            {},
            {"attributes": ["id", "name", "code", "account_id", "account__name"], "order": ["name"]},
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
        if data.get("account_id"):
            validateTenantRelationId(
                TransactionAccount,
                data["account_id"],
                request=request,
                label="Transaction account",
            )
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
        validateTenantRelationId(
            ExpenseCategory,
            data.get("category_id"),
            request=request,
            label="Expense category",
            required=True,
        )
        if money(data.get("amount")) <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Amount must be greater than 0.")
        if data.get("payment_type"):
            data["payment_type"] = PaymentTypeService.resolvePaymentType(
                data.get("payment_type"),
                request,
            )
        if data.get("shift_id"):
            validateTenantRelationId(
                CashierShift,
                data["shift_id"],
                request=request,
                label="Cashier shift",
            )

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

        category = ExpenseCategory.objects.filter(
            id=expense.get("category_id"),
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
        ).first()
        AccountingService.ensureForRequest(request)
        expense_cash_account = TransactionAccount.objects.filter(
            account=ACCOUNT_CODES["expense_cash"],
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
        ).first()
        fallback_expense_account = TransactionAccount.objects.filter(
            account=ACCOUNT_CODES["direct_expenses"],
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
        ).first()
        expense_account_id = (
            category.account_id
            if category and category.account_id
            else fallback_expense_account.id if fallback_expense_account else None
        )
        if not expense_account_id or not expense_cash_account:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Configure an expense account before recording expenses.")
        group_code = f"expense:{expense['id']}"
        common = {
            "name": "Expense",
            "transaction_type": "expense",
            "amount": expense.get("amount"),
            "source_type": "expense",
            "source_id": expense["id"],
            "transaction_date": expense.get("expense_date"),
            "description": expense.get("note") or "Expense",
            "reference_number": expense.get("reference_number") or "",
            "event_key": "expense_paid",
            "group_code": group_code,
            "request": request,
        }
        AccountingService.record(account_id=expense_account_id, action_type="increase", **common)
        AccountingService.record(
            account_id=expense_cash_account.id,
            action_type="decrease",
            **common,
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
                type="expense_paid",
                transaction__group_id=expense["id"],
            )
            .filter(transaction__id__isnull=False)
            .select_related("transaction_account", "transaction")
        )
        for history in histories:
            reverse_action = "credit" if history.operation == "debit" else "debit"
            AccountingService.updateBalances(
                history.transaction_account_id,
                history.value,
                reverse_action,
                history.trigger_date or history.transaction.scheduled_date or history.created_at,
                request,
            )
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
        count = commonQuery.updateStatusById(ExpenseEntry, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense not found.")
        return successResponse("Expense status updated successfully.", data={"updated_count": count, "status": status})
