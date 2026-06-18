# type:ignore
from django.db import transaction
from django.db.models import F
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone

from apps.accounting.models import (
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
from apps.common.helpers import decimalValue as money
from apps.common.responses import successResponse


ACCOUNT_BLUEPRINTS = [
    ("fixed_assets", "Fixed Assets", "1001-assets-fixed-assets", "assets", None),
    ("current_assets", "Current Assets", "1002-assets-current-assets", "assets", None),
    ("inventory", "Inventory Account", "1003-assets-inventory-account", "assets", None),
    ("current_liabilities", "Current Liabilities", "2001-liabilities-current-liabilities", "liabilities", None),
    ("sales_revenue", "Sales Revenues", "4001-revenues-sales-revenues", "revenues", None),
    ("direct_expenses", "Direct Expenses", "5001-expenses-direct-expenses", "expenses", None),
    ("expense_cash", "Expenses Cash", "1004-assets-expenses-cash", "assets", "current_assets"),
    ("procurement_cash", "Procurement Cash", "1005-assets-procurement-cash", "assets", "current_assets"),
    ("procurement_payable", "Procurement Payable", "2002-liabilities-procurement-payable", "liabilities", "current_liabilities"),
    ("receivables", "Receivables", "1006-assets-receivables", "assets", "current_assets"),
    ("sales_cash", "Sales", "1007-assets-sales", "assets", "current_assets"),
    ("refunds", "Refunds", "4002-revenues-refunds", "revenues", "sales_revenue"),
    ("sales_cogs", "Sales COGS", "5002-expenses-sales-cogs", "expenses", "direct_expenses"),
    ("operating_expenses", "Operating Expenses", "5003-expenses-operating-expenses", "expenses", "direct_expenses"),
    ("rent_expenses", "Rent Expenses", "5004-expenses-rent-expenses", "expenses", "direct_expenses"),
    ("other_expenses", "Other Expenses", "5005-expenses-other-expenses", "expenses", "direct_expenses"),
    ("salaries_wages", "Salaries And Wages", "5006-expenses-salaries-and-wages", "expenses", "direct_expenses"),
]

ACCOUNT_CODES = {key: account for key, _name, account, _category, _parent in ACCOUNT_BLUEPRINTS}

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
    ("order_paid_voided", "Paid Order Voided"),
    ("order_unpaid_voided", "Unpaid Order Voided"),
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
    ("order_paid_voided", "increase", "sales_cash", "decrease", "sales_cash"),
    ("order_unpaid_voided", "decrease", "sales_revenue", "decrease", "receivables"),
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
    SYSTEM_ACCOUNT_ALIASES = {
        "cash": "sales_cash",
        "cash-payment": "sales_cash",
        "bank": "sales_cash",
        "bank-payment": "sales_cash",
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
        for key, name, account, category_identifier, parent_key in ACCOUNT_BLUEPRINTS:
            transaction_account, _created = TransactionAccount.objects.get_or_create(
                company_id=company.id,
                branch_id=branch.id,
                account=account,
                defaults={
                    "name": name,
                    "category_identifier": category_identifier,
                    "description": "Default NexoPOS accounting account.",
                },
            )
            accounts[key] = transaction_account

        for key, _name, account, category_identifier, parent_key in ACCOUNT_BLUEPRINTS:
            update_fields = []
            if accounts[key].name != dict((item[0], item[1]) for item in ACCOUNT_BLUEPRINTS)[key]:
                accounts[key].name = dict((item[0], item[1]) for item in ACCOUNT_BLUEPRINTS)[key]
                update_fields.append("name")
            if accounts[key].account != account:
                accounts[key].account = account
                update_fields.append("account")
            if accounts[key].category_identifier != category_identifier:
                accounts[key].category_identifier = category_identifier
                update_fields.append("category_identifier")
            if parent_key and accounts[key].sub_category_id != accounts[parent_key].id:
                accounts[key].sub_category = accounts[parent_key]
                update_fields.append("sub_category")
            if update_fields:
                accounts[key].save(update_fields=[*update_fields, "updated_at"])

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
                        on=event_key,
                        action=action,
                        account=accounts[account_key],
                        do=offset_action,
                        offset_account=accounts[offset_key],
                        locked=True,
                    )
                    for event_key, action, account_key, offset_action, offset_key in DEFAULT_RULES
                ]
            )

        from apps.settingsapi.services import OptionSettingService

        OptionSettingService.ensureOptionValue(
            company,
            branch,
            "ns_accounting_default_paid_expense_offset_account",
            accounts["expense_cash"].id,
        )

        return accounts

    @staticmethod
    def ensureForRequest(request):
        return AccountingService.ensureDefaultAccounting(request.user.company, request.user.branch)

    @staticmethod
    def accountForPaymentType(payment_type):
        payment_accounts = {
            "cash": "cash",
            "cash-payment": "cash-payment",
            "bank": "bank",
            "bank-payment": "bank-payment",
            "online": "online",
            "card": "card",
            "partial": "customer_credit",
        }
        if payment_type in payment_accounts:
            return payment_accounts[payment_type]
        return "cash"

    @staticmethod
    def getOrCreateSystemAccount(code, request):
        account_key = AccountingService.SYSTEM_ACCOUNT_ALIASES.get(code)
        if not account_key:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid accounting account.")
        AccountingService.ensureForRequest(request)
        account = TransactionAccount.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            account=ACCOUNT_CODES[account_key],
            status__in=[0, 1],
        ).values().first()
        if not account:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Accounting account not found.")
        return account

    @staticmethod
    def updateBalances(account_id, amount, operation, transaction_date, request):
        amount = money(amount)
        balance_date = transaction_date.date()
        previous_day = (
            TransactionBalanceDay.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                date__lt=balance_date,
            )
            .order_by("-date")
            .first()
        )
        opening_balance = money(previous_day.closing_balance if previous_day else 0)
        day, _ = TransactionBalanceDay.objects.select_for_update().get_or_create(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            date=balance_date,
            defaults={"opening_balance": opening_balance, "closing_balance": opening_balance},
        )
        if operation == "credit":
            day.income = F("income") + amount
        else:
            day.expense = F("expense") + amount
        day.save(update_fields=["income", "expense", "updated_at"])
        day.refresh_from_db(fields=["opening_balance", "income", "expense"])
        day.closing_balance = money(day.opening_balance) + money(day.income) - money(day.expense)
        day.save(update_fields=["closing_balance", "updated_at"])

        month_date = balance_date.replace(day=1)
        previous_month = (
            TransactionBalanceMonth.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                date__lt=month_date,
            )
            .order_by("-date")
            .first()
        )
        month_opening_balance = money(previous_month.closing_balance if previous_month else 0)
        month, _ = TransactionBalanceMonth.objects.select_for_update().get_or_create(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            date=month_date,
            defaults={"opening_balance": month_opening_balance, "closing_balance": month_opening_balance},
        )
        if operation == "credit":
            month.income = F("income") + amount
        else:
            month.expense = F("expense") + amount
        month.save(update_fields=["income", "expense", "updated_at"])
        month.refresh_from_db(fields=["opening_balance", "income", "expense"])
        month.closing_balance = money(month.opening_balance) + money(month.income) - money(month.expense)
        month.save(update_fields=["closing_balance", "updated_at"])

        return day.opening_balance, day.closing_balance

    @staticmethod
    def record(
        *,
        account_code=None,
        account_id=None,
        name,
        transaction_type="",
        action_type="increase",
        amount=0,
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
        procurement_id=None,
        order_refund_id=None,
        order_refund_product_id=None,
        order_id=None,
        order_product_id=None,
        register_history_id=None,
        customer_account_history_id=None,
        request=None,
    ):
        amount = money(amount)
        if amount <= 0:
            return None
        operation = {"increase": "credit", "decrease": "debit"}.get(action_type, action_type)
        if operation not in ["credit", "debit"]:
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
                    "value": amount,
                    "description": description,
                    "recurring": is_recurring,
                    "type": Transaction.TYPE_RECURRING if is_recurring else Transaction.TYPE_DIRECT,
                    "group_id": source_id,
                    "occurrence": recurring_rule,
                    "scheduled_date": normalizeTransactionDate(next_run_at) if next_run_at else tx_date,
                },
                request=request,
                tenant_config=True,
            )
            AccountingService.updateBalances(account["id"], amount, operation, tx_date, request)
            history = commonQuery.createRecord(
                TransactionHistory,
                {
                    "transaction_id": transaction_record["id"],
                    "operation": operation,
                    "transaction_account_id": account["id"],
                    "rule_id": rule_id,
                    "procurement_id": source_id if source_type == "purchase" else procurement_id,
                    "order_refund_id": source_id if source_type == "refund" else order_refund_id,
                    "order_refund_product_id": order_refund_product_id,
                    "order_id": source_id if source_type == "sale" else order_id,
                    "order_product_id": order_product_id,
                    "register_history_id": source_id if source_type == "cash_register" else register_history_id,
                    "customer_account_history_id": source_id if source_type == "customer_credit" else customer_account_history_id,
                    "name": name,
                    "type": event_key or transaction_type or source_type,
                    "value": amount,
                    "trigger_date": tx_date,
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
            on=event_key,
            status=0,
        ).order_by("id")
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
                        action_type=rule.do,
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
                    "account": account.account,
                    "category_identifier": account.category_identifier,
                }
                for account in accounts.values()
            ],
        )


class TransactionAccountService:
    @staticmethod
    def create(data, request):
        parent_id = data.get("sub_category_id")
        if parent_id and not TransactionAccount.objects.filter(
            id=parent_id,
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
        ).exists():
            raise api_error(404, ErrorCodes.NOT_FOUND, "Parent account not found.")
        if parent_id:
            parent = TransactionAccount.objects.filter(
                id=parent_id,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                status__in=[0, 1],
            ).first()
            if parent and parent.sub_category_id:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Three level of accounts is not allowed.")

        if not data.get("category_identifier"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Accounting category is required.")
        if not data.get("account"):
            siblings = TransactionAccount.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                category_identifier=data.get("category_identifier"),
            ).count()
            data["account"] = f"{str(siblings + 1).zfill(4)}-{data['category_identifier']}-{data['name'].lower().replace(' ', '-')}"
        account = commonQuery.createRecord(TransactionAccount, data, request=request, tenant_config=True)
        return successResponse("Transaction account created successfully.", data=account)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            TransactionAccount,
            data,
            [
                ["name", True, True],
                ["account", True, True],
                ["category_identifier", True, True],
            ],
            {
                "attributes": [
                    "id",
                    "name",
                    "account",
                    "category_identifier",
                    "sub_category_id",
                    "sub_category__name",
                    "description",
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
                "attributes": [
                    "id",
                    "name",
                    "account",
                    "category_identifier",
                    "sub_category_id",
                    "sub_category__name",
                ],
                "order": ["category_identifier", "name"],
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
                "on": rule.on,
                "event_label": labels.get(rule.on, rule.on.replace("_", " ").title()),
                "action": rule.action,
                "account_id": rule.account_id,
                "account_name": rule.account.name,
                "do": rule.do,
                "offset_account_id": rule.offset_account_id,
                "offset_account_name": rule.offset_account.name,
                "locked": rule.locked,
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
        if "event_key" in data and "on" not in data:
            data["on"] = data.pop("event_key")
        if "offset_action" in data and "do" not in data:
            data["do"] = data.pop("offset_action")
        TransactionRuleService.validateAccounts(data, request)
        rule = commonQuery.createRecord(TransactionActionRule, data, request=request, tenant_config=True)
        return successResponse("Accounting rule created successfully.", data=rule)

    @staticmethod
    def update(rule_id, data, request):
        if "event_key" in data and "on" not in data:
            data["on"] = data.pop("event_key")
        if "offset_action" in data and "do" not in data:
            data["do"] = data.pop("offset_action")
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
            [["name", True, True], ["type", True, True], ["description", True, True]],
            {
                "attributes": [
                    "id",
                    "account_id",
                    "account__name",
                    "name",
                    "description",
                    "media_id",
                    "value",
                    "recurring",
                    "type",
                    "active",
                    "group_id",
                    "occurrence",
                    "occurrence_value",
                    "scheduled_date",
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
            [["operation", True, True], ["type", True, True], ["name", True, True]],
            {
                "attributes": [
                    "id",
                    "transaction_id",
                    "transaction__name",
                    "operation",
                    "transaction_account_id",
                    "transaction_account__name",
                    "rule_id",
                    "procurement_id",
                    "order_refund_id",
                    "order_refund_product_id",
                    "order_id",
                    "order_product_id",
                    "register_history_id",
                    "customer_account_history_id",
                    "name",
                    "type",
                    "value",
                    "trigger_date",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Transaction history retrieved successfully.", data=result)
