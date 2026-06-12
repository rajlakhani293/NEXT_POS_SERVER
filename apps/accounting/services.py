# type:ignore
from django.db import transaction
from django.db.models import F
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone

from apps.accounting.models import (
    ActiveTransactionHistory,
    Transaction,
    TransactionAccount,
    TransactionBalanceDay,
    TransactionBalanceMonth,
    TransactionHistory,
)
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode, decimalValue as money
from apps.common.responses import successResponse


def normalizeTransactionDate(value):
    if not value:
        return timezone.now()
    if hasattr(value, "hour"):
        return value
    if hasattr(value, "year"):
        return timezone.make_aware(timezone.datetime.combine(value, timezone.datetime.min.time()))
    parsed_datetime = parse_datetime(str(value))
    if parsed_datetime:
        return parsed_datetime if timezone.is_aware(parsed_datetime) else timezone.make_aware(parsed_datetime)
    parsed_date = parse_date(str(value))
    if parsed_date:
        return timezone.make_aware(timezone.datetime.combine(parsed_date, timezone.datetime.min.time()))
    return timezone.now()


class AccountingService:
    SYSTEM_ACCOUNTS = {
        "cash": {"name": "Cash", "account_type": "asset"},
        "bank": {"name": "Bank", "account_type": "asset"},
        "online": {"name": "Online Payment", "account_type": "asset"},
        "card": {"name": "Card Payment", "account_type": "asset"},
        "sales_income": {"name": "Sales Income", "account_type": "income"},
        "purchase_payable": {"name": "Purchase Payable", "account_type": "liability"},
        "expense": {"name": "Expenses", "account_type": "expense"},
        "customer_credit": {"name": "Customer Credit", "account_type": "liability"},
        "adjustment": {"name": "Stock / Cash Adjustment", "account_type": "expense"},
    }

    @staticmethod
    def accountForPaymentType(payment_type):
        payment_accounts = {
            "cash": "cash",
            "cash-payment": "cash",
            "bank": "bank",
            "bank-payment": "bank",
            "online": "bank",
            "card": "bank",
            "account-payment": "customer_credit",
        }
        if payment_type in payment_accounts:
            return payment_accounts[payment_type]
        return "bank"

    @staticmethod
    def getOrCreateSystemAccount(code, request):
        config = AccountingService.SYSTEM_ACCOUNTS.get(code)
        if not config:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid accounting account.")
        account = commonQuery.findOneRecord(
            TransactionAccount,
            {"code": code},
            request=request,
            tenant_config=True,
        )
        if account:
            return account
        return commonQuery.createRecord(
            TransactionAccount,
            {
                "name": config["name"],
                "code": code,
                "account_type": config["account_type"],
                "description": "System generated account.",
                "is_system": True,
            },
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def updateBalances(account_id, amount, action_type, transaction_date, request):
        amount = money(amount)
        account = TransactionAccount.objects.select_for_update().get(id=account_id)
        balance_before = money(account.current_balance)
        balance_after = balance_before + amount if action_type == "credit" else balance_before - amount
        account.current_balance = balance_after
        account.save(update_fields=["current_balance", "updated_at"])

        balance_date = transaction_date.date()
        day, _ = TransactionBalanceDay.objects.select_for_update().get_or_create(
            company_id=account.company_id,
            branch_id=account.branch_id,
            account_id=account_id,
            balance_date=balance_date,
            defaults={"opening_balance": balance_before, "closing_balance": balance_before},
        )
        if action_type == "credit":
            day.total_credit = F("total_credit") + amount
        else:
            day.total_debit = F("total_debit") + amount
        day.closing_balance = balance_after
        day.save(update_fields=["total_credit", "total_debit", "closing_balance", "updated_at"])

        month, _ = TransactionBalanceMonth.objects.select_for_update().get_or_create(
            company_id=account.company_id,
            branch_id=account.branch_id,
            account_id=account_id,
            year=balance_date.year,
            month=balance_date.month,
            defaults={"opening_balance": balance_before, "closing_balance": balance_before},
        )
        if action_type == "credit":
            month.total_credit = F("total_credit") + amount
        else:
            month.total_debit = F("total_debit") + amount
        month.closing_balance = balance_after
        month.save(update_fields=["total_credit", "total_debit", "closing_balance", "updated_at"])

        return balance_before, balance_after

    @staticmethod
    def record(
        *,
        account_code=None,
        account_id=None,
        name,
        transaction_type,
        action_type,
        amount,
        source_type="manual",
        source_id=None,
        transaction_date=None,
        description="",
        reference_number="",
        request=None,
    ):
        amount = money(amount)
        if amount <= 0:
            return None
        if action_type not in ["credit", "debit"]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Action type must be credit or debit.")

        with transaction.atomic():
            if account_id:
                account = commonQuery.findOneRecord(TransactionAccount, account_id, request=request, tenant_config=True)
                if account is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction account not found.")
            else:
                account = AccountingService.getOrCreateSystemAccount(account_code, request)

            tx_date = normalizeTransactionDate(transaction_date)
            transaction_record = commonQuery.createRecord(
                Transaction,
                {
                    "account_id": account["id"],
                    "name": name,
                    "transaction_type": transaction_type,
                    "source_type": source_type,
                    "source_id": source_id,
                    "value": amount,
                    "transaction_date": tx_date,
                    "description": description,
                    "reference_number": reference_number,
                    "created_by_id": getattr(request, "user", None).id if request and getattr(request, "user", None) else None,
                },
                request=request,
                tenant_config=True,
            )
            balance_before, balance_after = AccountingService.updateBalances(account["id"], amount, action_type, tx_date, request)
            history = commonQuery.createRecord(
                TransactionHistory,
                {
                    "transaction_id": transaction_record["id"],
                    "account_id": account["id"],
                    "action_type": action_type,
                    "amount": amount,
                    "balance_before": balance_before,
                    "balance_after": balance_after,
                    "source_type": source_type,
                    "source_id": source_id,
                    "note": description,
                },
                request=request,
                tenant_config=True,
            )
            commonQuery.createRecord(
                ActiveTransactionHistory,
                {
                    "transaction_history_id": history["id"],
                    "transaction_id": transaction_record["id"],
                    "account_id": account["id"],
                    "action_type": action_type,
                    "amount": amount,
                    "source_type": source_type,
                    "source_id": source_id,
                },
                request=request,
                tenant_config=True,
            )
            return {**transaction_record, "history": history}

    @staticmethod
    def bootstrapSystemAccounts(request):
        accounts = [AccountingService.getOrCreateSystemAccount(code, request) for code in AccountingService.SYSTEM_ACCOUNTS]
        return successResponse("Accounting accounts bootstrapped successfully.", data=accounts)


class TransactionAccountService:
    @staticmethod
    def create(data, request):
        data["code"] = buildCode(TransactionAccount, data.get("name"), data.get("code"), request)
        opening_balance = money(data.pop("opening_balance", 0))
        account = commonQuery.createRecord(TransactionAccount, data, request=request, tenant_config=True)
        if opening_balance > 0:
            AccountingService.record(
                account_id=account["id"],
                name="Opening Balance",
                transaction_type="adjustment",
                action_type="credit",
                amount=opening_balance,
                source_type="manual",
                source_id=account["id"],
                description="Opening balance",
                request=request,
            )
        return successResponse("Transaction account created successfully.", data=account)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            TransactionAccount,
            data,
            [["name", True, True], ["code", True, True], ["account_type", True, True]],
            {"attributes": ["id", "name", "code", "account_type", "current_balance", "is_system", "status"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Transaction accounts retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            TransactionAccount,
            {},
            {"attributes": ["id", "name", "code", "account_type", "current_balance"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getById(account_id, request):
        account = commonQuery.findOneRecord(TransactionAccount, account_id, request=request, tenant_config=True)
        if account is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction account not found.")
        return successResponse("Transaction account retrieved successfully.", data=account)

    @staticmethod
    def update(account_id, data, request):
        if data.get("code"):
            data["code"] = buildCode(TransactionAccount, data.get("name") or "Account", data.get("code"), request, exclude_id=account_id)
        updated = commonQuery.updateRecordById(TransactionAccount, account_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction account not found.")
        return successResponse("Transaction account updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(TransactionAccount, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction account not found.")
        return successResponse("Transaction accounts deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(TransactionAccount, data.get("ids"), status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction account not found.")
        return successResponse("Transaction account status updated successfully.", data={"updated_count": count, "status": status})


class TransactionService:
    @staticmethod
    def createManual(data, request):
        record = AccountingService.record(
            account_id=data.get("account_id"),
            name=data.get("name"),
            transaction_type=data.get("transaction_type"),
            action_type=data.get("action_type"),
            amount=data.get("amount"),
            source_type="manual",
            transaction_date=data.get("transaction_date") or timezone.now(),
            description=data.get("description") or "",
            reference_number=data.get("reference_number") or "",
            request=request,
        )
        return successResponse("Transaction created successfully.", data=record)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            Transaction,
            data,
            [["name", True, True], ["transaction_type", True, True], ["source_type", True, True], ["reference_number", True, True]],
            {
                "attributes": [
                    "id",
                    "account_id",
                    "account__name",
                    "name",
                    "transaction_type",
                    "source_type",
                    "source_id",
                    "value",
                    "transaction_date",
                    "reference_number",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Transactions retrieved successfully.", data=result)

    @staticmethod
    def history(data, request):
        result = commonQuery.fetchPaginatedData(
            TransactionHistory,
            data,
            [["action_type", True, True], ["source_type", True, True], ["note", True, True]],
            {
                "attributes": [
                    "id",
                    "transaction_id",
                    "transaction__name",
                    "account_id",
                    "account__name",
                    "action_type",
                    "amount",
                    "balance_before",
                    "balance_after",
                    "source_type",
                    "source_id",
                    "note",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Transaction history retrieved successfully.", data=result)
