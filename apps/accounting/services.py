# type:ignore
from django.db import transaction
from django.db.models import F
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone

from apps.accounting.models import (
    AccountingSetting,
    ActiveTransactionHistory,
    Transaction,
    TransactionAccount,
    TransactionActionRule,
    TransactionBalanceDay,
    TransactionBalanceMonth,
    TransactionHistory,
)
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode, decimalValue as money
from apps.common.responses import successResponse


ACCOUNT_BLUEPRINTS = [
    ("fixed_assets", "Fixed Assets", "1001-assets-fixed-assets", "asset", None),
    ("current_assets", "Current Assets", "1002-assets-current-assets", "asset", None),
    ("inventory", "Inventory Account", "1003-assets-inventory-account", "asset", None),
    ("current_liabilities", "Current Liabilities", "2001-liabilities-current-liabilities", "liability", None),
    ("sales_revenue", "Sales Revenues", "4001-revenues-sales-revenues", "income", None),
    ("direct_expenses", "Direct Expenses", "5001-expenses-direct-expenses", "expense", None),
    ("expense_cash", "Expenses Cash", "1004-assets-expenses-cash", "asset", "current_assets"),
    ("procurement_cash", "Procurement Cash", "1005-assets-procurement-cash", "asset", "current_assets"),
    ("procurement_payable", "Procurement Payable", "2002-liabilities-procurement-payable", "liability", "current_liabilities"),
    ("receivables", "Receivables", "1006-assets-receivables", "asset", "current_assets"),
    ("sales_cash", "Sales", "1007-assets-sales", "asset", "current_assets"),
    ("refunds", "Refunds", "4002-revenues-refunds", "income", "sales_revenue"),
    ("sales_cogs", "Sales COGS", "5002-expenses-sales-cogs", "expense", "direct_expenses"),
    ("operating_expenses", "Operating Expenses", "5003-expenses-operating-expenses", "expense", "direct_expenses"),
    ("rent_expenses", "Rent Expenses", "5004-expenses-rent-expenses", "expense", "direct_expenses"),
    ("other_expenses", "Other Expenses", "5005-expenses-other-expenses", "expense", "direct_expenses"),
    ("salaries_wages", "Salaries And Wages", "5006-expenses-salaries-and-wages", "expense", "direct_expenses"),
]

ACCOUNT_CODES = {key: code for key, _name, code, _type, _parent in ACCOUNT_BLUEPRINTS}

EVENT_OPTIONS = [
    ("procurement_paid", "Procurement Paid"),
    ("procurement_unpaid", "Procurement Unpaid"),
    ("procurement_from_unpaid_to_paid", "Paid Procurement From Unpaid"),
    ("order_paid", "Order Paid"),
    ("order_unpaid", "Order Unpaid"),
    ("order_refunded", "Order Refund"),
    ("order_partially_paid", "Order Partially Paid"),
    ("order_partially_refunded", "Order Partially Refunded"),
    ("order_from_unpaid_to_paid", "Order From Unpaid To Paid"),
    ("paid_order_voided", "Paid Order Voided"),
    ("unpaid_order_voided", "Unpaid Order Voided"),
    ("order_cogs", "Order COGS"),
    ("product_damaged", "Product Damaged"),
    ("product_returned", "Product Returned"),
]

DEFAULT_RULES = [
    ("procurement_unpaid", "increase", "inventory", "increase", "procurement_payable"),
    ("procurement_paid", "increase", "inventory", "decrease", "procurement_cash"),
    ("procurement_paid", "increase", "expense_cash", "decrease", "procurement_cash"),
    ("procurement_from_unpaid_to_paid", "decrease", "procurement_payable", "decrease", "procurement_cash"),
    ("order_unpaid", "increase", "receivables", "increase", "sales_revenue"),
    ("order_unpaid", "increase", "expense_cash", "decrease", "inventory"),
    ("order_from_unpaid_to_paid", "decrease", "sales_cash", "increase", "receivables"),
    ("order_paid", "increase", "sales_cash", "decrease", "receivables"),
    ("order_refunded", "decrease", "sales_revenue", "decrease", "sales_cash"),
    ("order_cogs", "increase", "sales_cogs", "decrease", "inventory"),
    ("paid_order_voided", "increase", "sales_cash", "decrease", "sales_cash"),
    ("unpaid_order_voided", "decrease", "sales_revenue", "decrease", "receivables"),
]


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

    SYSTEM_ACCOUNT_ALIASES = {
        "cash": "sales_cash",
        "bank": "sales_cash",
        "online": "sales_cash",
        "card": "sales_cash",
        "sales_income": "sales_revenue",
        "purchase_payable": "procurement_payable",
        "expense": "direct_expenses",
        "customer_credit": "receivables",
        "adjustment": "other_expenses",
    }

    @staticmethod
    def ensureDefaultAccounting(company, branch):
        accounts = {}
        for key, name, code, account_type, parent_key in ACCOUNT_BLUEPRINTS:
            account, _created = TransactionAccount.objects.get_or_create(
                company_id=company.id,
                branch_id=branch.id,
                code=code,
                defaults={
                    "name": name,
                    "account_type": account_type,
                    "is_system": True,
                    "is_locked": True,
                    "description": "Default NexoPOS accounting account.",
                },
            )
            accounts[key] = account

        for key, _name, _code, _type, parent_key in ACCOUNT_BLUEPRINTS:
            if parent_key and accounts[key].parent_id != accounts[parent_key].id:
                accounts[key].parent = accounts[parent_key]
                accounts[key].save(update_fields=["parent", "updated_at"])

        if not TransactionActionRule.objects.filter(
            company_id=company.id,
            branch_id=branch.id,
            status__in=[0, 1],
        ).exists():
            TransactionActionRule.objects.bulk_create(
                [
                    TransactionActionRule(
                        company_id=company.id,
                        branch_id=branch.id,
                        event_key=event_key,
                        action=action,
                        account=accounts[account_key],
                        offset_action=offset_action,
                        offset_account=accounts[offset_key],
                        is_system=True,
                        sort_order=index,
                    )
                    for index, (event_key, action, account_key, offset_action, offset_key) in enumerate(DEFAULT_RULES, 1)
                ]
            )

        setting, setting_created = AccountingSetting.objects.get_or_create(
            company_id=company.id,
            branch_id=branch.id,
            defaults={
                "paid_expense_offset_account": accounts["expense_cash"],
                "sales_revenue_account": accounts["sales_revenue"],
                "order_cash_account": accounts["sales_cash"],
                "receivable_account": accounts["receivables"],
                "cogs_account": accounts["sales_cogs"],
                "inventory_account": accounts["inventory"],
                "procurement_cash_account": accounts["procurement_cash"],
                "procurement_payable_account": accounts["procurement_payable"],
            },
        )
        if setting_created:
            setting.expense_accounts.set(
                [
                    accounts["direct_expenses"],
                    accounts["operating_expenses"],
                    accounts["rent_expenses"],
                    accounts["other_expenses"],
                    accounts["salaries_wages"],
                ]
            )
        return accounts

    @staticmethod
    def ensureForRequest(request):
        return AccountingService.ensureDefaultAccounting(request.user.company, request.user.branch)

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
        account_key = AccountingService.SYSTEM_ACCOUNT_ALIASES.get(code)
        if not account_key:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid accounting account.")
        AccountingService.ensureForRequest(request)
        account = TransactionAccount.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            code=ACCOUNT_CODES[account_key],
            status__in=[0, 1],
        ).values().first()
        if not account:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Accounting account not found.")
        return account

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
        event_key="",
        group_code="",
        rule_id=None,
        is_recurring=False,
        recurring_rule="",
        next_run_at=None,
        request=None,
    ):
        amount = money(amount)
        if amount <= 0:
            return None
        action_type = {"increase": "credit", "decrease": "debit"}.get(action_type, action_type)
        if action_type not in ["credit", "debit"]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Action type must be increase or decrease.")

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
                    "event_key": event_key,
                    "group_code": group_code,
                    "value": amount,
                    "transaction_date": tx_date,
                    "description": description,
                    "reference_number": reference_number,
                    "is_recurring": is_recurring,
                    "recurring_rule": recurring_rule,
                    "next_run_at": normalizeTransactionDate(next_run_at) if next_run_at else None,
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
                    "rule_id": rule_id,
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
    def reflectEvent(
        event_key,
        amount,
        *,
        name,
        transaction_type,
        source_type,
        source_id,
        transaction_date=None,
        description="",
        reference_number="",
        request,
    ):
        amount = money(amount)
        if amount <= 0:
            return []
        AccountingService.ensureForRequest(request)
        rules = TransactionActionRule.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            event_key=event_key,
            status=0,
        ).order_by("sort_order", "id")
        group_code = f"{event_key}:{source_type}:{source_id or 'manual'}:{timezone.now().timestamp()}"
        records = []
        with transaction.atomic():
            for rule in rules:
                common = {
                    "name": name,
                    "transaction_type": transaction_type,
                    "amount": amount,
                    "source_type": source_type,
                    "source_id": source_id,
                    "transaction_date": transaction_date,
                    "description": description,
                    "reference_number": reference_number,
                    "event_key": event_key,
                    "group_code": group_code,
                    "rule_id": rule.id,
                    "request": request,
                }
                records.append(
                    AccountingService.record(
                        account_id=rule.account_id,
                        action_type=rule.action,
                        **common,
                    )
                )
                records.append(
                    AccountingService.record(
                        account_id=rule.offset_account_id,
                        action_type=rule.offset_action,
                        **common,
                    )
                )
        return records

    @staticmethod
    def bootstrapSystemAccounts(request):
        accounts = AccountingService.ensureForRequest(request)
        return successResponse(
            "Accounting accounts bootstrapped successfully.",
            data=[
                {
                    "id": account.id,
                    "name": account.name,
                    "code": account.code,
                    "account_type": account.account_type,
                }
                for account in accounts.values()
            ],
        )


class TransactionAccountService:
    @staticmethod
    def create(data, request):
        parent_id = data.get("parent_id")
        if parent_id and not TransactionAccount.objects.filter(
            id=parent_id,
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
        ).exists():
            raise api_error(404, ErrorCodes.NOT_FOUND, "Parent account not found.")
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
            {
                "attributes": [
                    "id",
                    "name",
                    "code",
                    "account_type",
                    "parent_id",
                    "parent__name",
                    "current_balance",
                    "is_system",
                    "is_locked",
                    "status",
                ]
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Transaction accounts retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        data = commonQuery.findAllRecords(
            TransactionAccount,
            {},
            {
                "attributes": ["id", "name", "code", "account_type", "parent_id", "parent__name", "current_balance"],
                "order": ["account_type", "name"],
            },
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
        account = TransactionAccount.objects.filter(
            id=account_id,
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
        ).first()
        if account is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction account not found.")
        if account.is_locked:
            data.pop("code", None)
            data.pop("account_type", None)
            data.pop("parent_id", None)
        if data.get("code"):
            data["code"] = buildCode(TransactionAccount, data.get("name") or "Account", data.get("code"), request, exclude_id=account_id)
        updated = commonQuery.updateRecordById(TransactionAccount, account_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction account not found.")
        return successResponse("Transaction account updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        protected = TransactionAccount.objects.filter(
            id__in=data.get("ids") or [],
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            is_locked=True,
        ).exists()
        if protected:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Default accounting accounts cannot be deleted.")
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


class TransactionRuleService:
    @staticmethod
    def eventOptions():
        return successResponse(
            "Accounting actions retrieved successfully.",
            data=[{"value": value, "label": label} for value, label in EVENT_OPTIONS],
        )

    @staticmethod
    def getAll(request):
        AccountingService.ensureForRequest(request)
        rules = TransactionActionRule.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
        ).select_related("account", "offset_account")
        labels = dict(EVENT_OPTIONS)
        data = [
            {
                "id": rule.id,
                "event_key": rule.event_key,
                "event_label": labels.get(rule.event_key, rule.event_key.replace("_", " ").title()),
                "action": rule.action,
                "account_id": rule.account_id,
                "account_name": rule.account.name,
                "offset_action": rule.offset_action,
                "offset_account_id": rule.offset_account_id,
                "offset_account_name": rule.offset_account.name,
                "is_system": rule.is_system,
                "is_locked": rule.is_locked,
                "status": rule.status,
            }
            for rule in rules
        ]
        return successResponse("Accounting rules retrieved successfully.", data=data)

    @staticmethod
    def validateAccounts(data, request):
        account_ids = {data.get("account_id"), data.get("offset_account_id")} - {None}
        found = set(
            TransactionAccount.objects.filter(
                id__in=account_ids,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                status__in=[0, 1],
            ).values_list("id", flat=True)
        )
        if found != account_ids:
            raise api_error(404, ErrorCodes.NOT_FOUND, "One or more transaction accounts were not found.")

    @staticmethod
    def create(data, request):
        TransactionRuleService.validateAccounts(data, request)
        data["sort_order"] = (
            TransactionActionRule.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
            ).count()
            + 1
        )
        rule = commonQuery.createRecord(TransactionActionRule, data, request=request, tenant_config=True)
        return successResponse("Accounting rule created successfully.", data=rule)

    @staticmethod
    def update(rule_id, data, request):
        TransactionRuleService.validateAccounts(data, request)
        updated = commonQuery.updateRecordById(
            TransactionActionRule,
            rule_id,
            data,
            request=request,
            tenant_config=True,
        )
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Accounting rule not found.")
        return successResponse("Accounting rule updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(
            TransactionActionRule,
            data.get("ids"),
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Accounting rule not found.")
        return successResponse("Accounting rule deleted successfully.")

    @staticmethod
    def reset(request):
        TransactionActionRule.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
        ).delete()
        AccountingService.ensureForRequest(request)
        return TransactionRuleService.getAll(request)


class AccountingSettingService:
    FIELDS = [
        "paid_expense_offset_account",
        "sales_revenue_account",
        "order_cash_account",
        "receivable_account",
        "cogs_account",
        "inventory_account",
        "procurement_cash_account",
        "procurement_payable_account",
    ]

    @staticmethod
    def getObject(request):
        AccountingService.ensureForRequest(request)
        return AccountingSetting.objects.prefetch_related("expense_accounts").get(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
        )

    @staticmethod
    def serialize(setting):
        data = {
            "id": setting.id,
            "expense_account_ids": list(setting.expense_accounts.values_list("id", flat=True)),
            "expense_accounts": list(setting.expense_accounts.values("id", "name", "code")),
        }
        for field in AccountingSettingService.FIELDS:
            account = getattr(setting, field)
            data[f"{field}_id"] = account.id
            data[field] = {"id": account.id, "name": account.name, "code": account.code}
        return data

    @staticmethod
    def get(request):
        return successResponse(
            "Accounting configuration retrieved successfully.",
            data=AccountingSettingService.serialize(AccountingSettingService.getObject(request)),
        )

    @staticmethod
    def update(data, request):
        expense_ids = list(data.pop("expense_account_ids", []))
        account_ids = set(expense_ids)
        account_ids.update(data.values())
        found = set(
            TransactionAccount.objects.filter(
                id__in=account_ids,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                status=0,
            ).values_list("id", flat=True)
        )
        if found != account_ids:
            raise api_error(404, ErrorCodes.NOT_FOUND, "One or more transaction accounts were not found.")
        setting = AccountingSettingService.getObject(request)
        for field in AccountingSettingService.FIELDS:
            setattr(setting, f"{field}_id", data[f"{field}_id"])
        setting.save()
        setting.expense_accounts.set(expense_ids)
        return successResponse(
            "Accounting configuration updated successfully.",
            data=AccountingSettingService.serialize(setting),
        )


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
            is_recurring=data.get("recurring", False),
            recurring_rule=data.get("recurring_rule") or "",
            next_run_at=data.get("next_run_at"),
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
                    "event_key",
                    "group_code",
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
