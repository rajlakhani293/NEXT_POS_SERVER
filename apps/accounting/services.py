# type:ignore
from types import SimpleNamespace
from datetime import timedelta
from django.db import transaction
from django.db.models import F, Q, Sum
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
from apps.common.tenantDefaults import ACCOUNT_BLUEPRINTS, DEFAULT_ACCOUNT_RULES, EVENT_OPTIONS


ACCOUNT_CODES = {key: account for key, _name, account, _category, _parent in ACCOUNT_BLUEPRINTS}


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
                    "description": "Default accounting account.",
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
                    for event_key, action, account_key, offset_action, offset_key in DEFAULT_ACCOUNT_RULES
                ]
            )

        from apps.common.tenantDefaults import ensureOptionValue

        ensureOptionValue(
            company,
            branch,
            "accounting_default_paid_expense_offset_account",
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
    def recomputeBalances(from_date, to_date, request):
        start = normalizeTransactionDate(from_date).date()
        end = normalizeTransactionDate(to_date).date()
        if start > end:
            start, end = end, start

        with transaction.atomic():
            TransactionBalanceDay.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                date__gte=start,
                date__lte=end,
            ).delete()
            TransactionBalanceMonth.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                date__gte=start.replace(day=1),
                date__lte=end.replace(day=1),
            ).delete()

            current_day = start
            previous_day = (
                TransactionBalanceDay.objects.filter(
                    company_id=request.user.company_id,
                    branch_id=request.user.branch_id,
                    date__lt=start,
                )
                .order_by("-date")
                .first()
            )
            opening_balance = money(previous_day.closing_balance if previous_day else 0)
            rebuilt_days = 0
            while current_day <= end:
                totals = TransactionHistory.objects.filter(
                    company_id=request.user.company_id,
                    branch_id=request.user.branch_id,
                    status=0,
                    transaction_status=TransactionHistory.STATUS_ACTIVE_TEXT,
                    trigger_date__date=current_day,
                ).aggregate(
                    income=Sum("value", filter=Q(operation=TransactionHistory.OPERATION_CREDIT)),
                    expense=Sum("value", filter=Q(operation=TransactionHistory.OPERATION_DEBIT)),
                )
                income = money(totals.get("income") or 0)
                expense = money(totals.get("expense") or 0)
                closing_balance = opening_balance + income - expense
                TransactionBalanceDay.objects.create(
                    user=request.user,
                    company_id=request.user.company_id,
                    branch_id=request.user.branch_id,
                    date=current_day,
                    opening_balance=opening_balance,
                    income=income,
                    expense=expense,
                    closing_balance=closing_balance,
                    status=0,
                )
                rebuilt_days += 1
                opening_balance = closing_balance
                current_day += timedelta(days=1)

            current_month = start.replace(day=1)
            end_month = end.replace(day=1)
            previous_month = (
                TransactionBalanceMonth.objects.filter(
                    company_id=request.user.company_id,
                    branch_id=request.user.branch_id,
                    date__lt=current_month,
                )
                .order_by("-date")
                .first()
            )
            month_opening_balance = money(previous_month.closing_balance if previous_month else 0)
            rebuilt_months = 0
            while current_month <= end_month:
                next_month = (current_month.replace(day=28) + timedelta(days=4)).replace(day=1)
                totals = TransactionBalanceDay.objects.filter(
                    company_id=request.user.company_id,
                    branch_id=request.user.branch_id,
                    date__gte=current_month,
                    date__lt=next_month,
                ).aggregate(
                    income=Sum("income"),
                    expense=Sum("expense"),
                )
                income = money(totals.get("income") or 0)
                expense = money(totals.get("expense") or 0)
                month_closing_balance = month_opening_balance + income - expense
                TransactionBalanceMonth.objects.create(
                    user=request.user,
                    company_id=request.user.company_id,
                    branch_id=request.user.branch_id,
                    date=current_month,
                    opening_balance=month_opening_balance,
                    income=income,
                    expense=expense,
                    closing_balance=month_closing_balance,
                    status=0,
                )
                rebuilt_months += 1
                month_opening_balance = month_closing_balance
                current_month = next_month

        return successResponse(
            "Accounting balances recomputed successfully.",
            data={
                "from_date": start,
                "to_date": end,
                "rebuilt_days": rebuilt_days,
                "rebuilt_months": rebuilt_months,
            },
        )

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
        order_payment_id=None,
        register_history_id=None,
        customer_account_history_id=None,
        is_reflection=False,
        reflection_source_id=None,
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
                    "order_payment_id": source_id if source_type == "order_payment" else order_payment_id,
                    "register_history_id": source_id if source_type == "cash_register" else register_history_id,
                    "customer_account_history_id": source_id if source_type == "customer_credit" else customer_account_history_id,
                    "name": name,
                    "type": event_key or transaction_type or source_type,
                    "value": amount,
                    "trigger_date": tx_date,
                    "transaction_status": TransactionHistory.STATUS_ACTIVE_TEXT,
                    "is_reflection": is_reflection,
                    "reflection_source_id": reflection_source_id,
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
                primary_record = AccountingService.record(
                    account_id=rule.account_id,
                    action_type=rule.action,
                    **common,
                )
                records.append(primary_record)
                primary_history_id = (primary_record or {}).get("history", {}).get("id")
                records.append(
                    AccountingService.record(
                        account_id=rule.offset_account_id,
                        action_type=rule.do,
                        is_reflection=True,
                        reflection_source_id=primary_history_id,
                        **common,
                    )
                )
        return records

    @staticmethod
    def reflectTransactionFromRule(history_id, request):
        history = commonQuery.findOneRecord(
            TransactionHistory,
            history_id,
            request=request,
            tenant_config=True,
        )
        if history is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction history not found.")
        if history.get("is_reflection"):
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Transaction history is already a reflection.")

        existing = commonQuery.findOneRecord(
            TransactionHistory,
            {"reflection_source_id": history["id"]},
            request=request,
            tenant_config=True,
        )
        if existing:
            return successResponse("Accounting reflection already exists.", data=existing)

        rule_id = history.get("rule_id")
        if not rule_id:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Transaction history has no accounting rule.")
        rule = commonQuery.findOneRecord(
            TransactionActionRule,
            rule_id,
            request=request,
            tenant_config=True,
        )
        if rule is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Accounting rule not found.")

        record = AccountingService.record(
            account_id=rule["offset_account_id"],
            action_type=rule.get("do") or ("decrease" if history.get("operation") == "credit" else "increase"),
            name=history.get("name") or "Accounting reflection",
            transaction_type=history.get("type") or "reflection",
            amount=history.get("value"),
            source_type="reflection",
            source_id=history["id"],
            transaction_date=history.get("trigger_date") or timezone.now(),
            event_key=history.get("type") or "",
            rule_id=rule["id"],
            procurement_id=history.get("procurement_id"),
            order_refund_id=history.get("order_refund_id"),
            order_refund_product_id=history.get("order_refund_product_id"),
            order_id=history.get("order_id"),
            order_product_id=history.get("order_product_id"),
            order_payment_id=history.get("order_payment_id"),
            register_history_id=history.get("register_history_id"),
            customer_account_history_id=history.get("customer_account_history_id"),
            is_reflection=True,
            reflection_source_id=history["id"],
            request=request,
        )
        return successResponse("Accounting reflection created successfully.", data=record)

    @staticmethod
    def deleteTransactionReflection(history_id, request):
        history = commonQuery.findOneRecord(
            TransactionHistory,
            history_id,
            request=request,
            tenant_config=True,
        )
        if history is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction history not found.")

        reflections = TransactionHistory.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            reflection_source_id=history["id"],
        ).exclude(status=2)
        reflection_dates = list(reflections.values_list("trigger_date", flat=True))
        deleted_count = reflections.delete()[0]
        if deleted_count:
            target_date = next((value for value in reflection_dates if value), history.get("trigger_date") or timezone.now())
            target_date = normalizeTransactionDate(target_date).date().isoformat()
            AccountingService.recomputeBalances(target_date, target_date, request)
        return successResponse("Accounting reflection deleted successfully.", data={"deleted_count": deleted_count})

    @staticmethod
    def recordRefundShipping(return_order_id, request):
        from apps.sales.models import Order, OrdersRefund

        refund = (
            OrdersRefund.objects.filter(
                id=return_order_id,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
            )
            .exclude(status=2)
            .first()
        )
        if refund is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Refund not found.")
        shipping_amount = money(refund.shipping)
        if shipping_amount <= 0:
            return successResponse("Refund has no shipping amount to record.", data=[])

        sale_order = (
            Order.objects.filter(
                id=refund.sale_order_id,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
            )
            .exclude(status=2)
            .first()
        )
        reference_number = sale_order.code if sale_order else str(return_order_id)
        records = AccountingService.reflectEvent(
            "order_refunded",
            shipping_amount,
            name=f"Refunded shipping {reference_number}",
            transaction_type="adjustment",
            source_type="refund",
            source_id=refund.id,
            transaction_date=refund.created_at,
            description="Shipping refunded from sale return",
            reference_number=reference_number,
            request=request,
        )
        return successResponse("Refund shipping transaction recorded successfully.", data=records)

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
    def requestFromJob(job):
        from apps.accounts.models import User

        user = User.objects.select_related("company", "branch").get(id=job.user_id)
        return SimpleNamespace(user=user)

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

    @staticmethod
    def _buildHistory(transaction_record, request, *, status=None, trigger_date=None):
        tx_date = normalizeTransactionDate(trigger_date or transaction_record.get("scheduled_date") or timezone.now())
        return commonQuery.createRecord(
            TransactionHistory,
            {
                "transaction_id": transaction_record["id"],
                "operation": "credit",
                "transaction_account_id": transaction_record["account_id"],
                "name": transaction_record["name"],
                "type": transaction_record.get("type") or Transaction.TYPE_DIRECT,
                "value": transaction_record.get("value") or 0,
                "trigger_date": tx_date,
                "transaction_status": status or TransactionHistory.STATUS_ACTIVE_TEXT,
            },
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def prepareTransactionHistory(transaction_id, request):
        transaction_record = commonQuery.findOneRecord(
            Transaction,
            transaction_id,
            request=request,
            tenant_config=True,
        )
        if transaction_record is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction not found.")
        history = TransactionService._buildHistory(
            transaction_record,
            request,
            status=TransactionHistory.STATUS_PENDING_TEXT,
            trigger_date=transaction_record.get("scheduled_date"),
        )
        return successResponse("Transaction history prepared successfully.", data=history)

    @staticmethod
    def executeDelayedTransaction(history_id, request):
        history = commonQuery.findOneRecord(
            TransactionHistory,
            history_id,
            request=request,
            tenant_config=True,
        )
        if history is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Transaction history not found.")
        if history.get("transaction_status") == TransactionHistory.STATUS_ACTIVE_TEXT:
            return successResponse("Transaction history already executed.", data=history)

        tx_date = normalizeTransactionDate(history.get("trigger_date") or timezone.now())
        AccountingService.updateBalances(
            history["transaction_account_id"],
            history.get("value") or 0,
            history.get("operation") or "credit",
            tx_date,
            request,
        )
        updated = commonQuery.updateRecordById(
            TransactionHistory,
            history_id,
            {
                "transaction_status": TransactionHistory.STATUS_ACTIVE_TEXT,
                "trigger_date": tx_date,
            },
            request=request,
            tenant_config=True,
        )
        from apps.settings.models import Notification

        Notification.objects.create(
            user_id=request.user.id,
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            identifier=f"scheduled-transaction-{history_id}",
            title="Scheduled Transaction",
            description=f'Transaction "{history.get("name")}" was executed as scheduled.',
            url="/reports/accounting",
            source="system",
            status=0,
        )
        return successResponse("Scheduled transaction executed successfully.", data=updated)

    @staticmethod
    def detectScheduledTransactions(data, request):
        from apps.settings.services import JobQueueService

        now = timezone.now()
        histories = TransactionHistory.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            transaction_status=TransactionHistory.STATUS_PENDING_TEXT,
            trigger_date__lte=now,
            status=0,
        ).values("id")
        queued_count = 0
        for history in histories:
            JobQueueService.enqueue(
                "execute_delayed_transaction",
                {"history_id": history["id"]},
                request=request,
            )
            queued_count += 1
        return successResponse("Scheduled transaction detection completed.", data={"queued_count": queued_count})

    @staticmethod
    def _recurringDueDate(transaction_record, base_date):
        occurrence = transaction_record.get("occurrence") or ""
        try:
            occurrence_value = int(transaction_record.get("occurrence_value") or 0)
        except (TypeError, ValueError):
            occurrence_value = 0

        if occurrence == "month_starts":
            return base_date.replace(day=1)
        if occurrence == "month_mid":
            return base_date.replace(day=15)
        if occurrence == "month_ends":
            next_month = (base_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            return next_month - timedelta(days=1)
        if occurrence == "x_before_month_ends":
            next_month = (base_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            return (next_month - timedelta(days=1)) - timedelta(days=occurrence_value)
        if occurrence == "x_after_month_starts":
            return base_date.replace(day=1) + timedelta(days=occurrence_value)
        if occurrence == "on_specific_day" and occurrence_value > 0:
            try:
                return base_date.replace(day=occurrence_value)
            except ValueError:
                return None
        if occurrence in ["every_x_minutes", "every_x_hours", "every_x_days"]:
            return base_date
        return None

    @staticmethod
    def triggerRecurringTransactions(data, request):
        base_datetime = normalizeTransactionDate((data or {}).get("date") or timezone.now())
        base_date = base_datetime.date()
        transactions = commonQuery.findAllRecords(
            Transaction,
            {"recurring": True, "active": True},
            {
                "attributes": [
                    "id",
                    "account_id",
                    "name",
                    "value",
                    "type",
                    "occurrence",
                    "occurrence_value",
                    "scheduled_date",
                ]
            },
            request=request,
            tenant_config=True,
        )
        processed = []
        skipped = []
        for transaction_record in transactions:
            due_date = TransactionService._recurringDueDate(transaction_record, base_date)
            if due_date != base_date:
                skipped.append(transaction_record["id"])
                continue
            exists = TransactionHistory.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                transaction_id=transaction_record["id"],
                trigger_date__date=base_date,
                status=0,
            ).exists()
            if exists:
                skipped.append(transaction_record["id"])
                continue
            history = TransactionService._buildHistory(
                transaction_record,
                request,
                status=TransactionHistory.STATUS_ACTIVE_TEXT,
                trigger_date=base_datetime,
            )
            AccountingService.updateBalances(
                transaction_record["account_id"],
                transaction_record.get("value") or 0,
                history.get("operation") or "credit",
                base_datetime,
                request,
            )
            processed.append(history)
        return successResponse(
            "Recurring transactions processed successfully.",
            data={"processed_count": len(processed), "skipped_count": len(skipped), "items": processed},
        )

    @staticmethod
    def enqueueBalanceRecompute(data, request):
        from apps.settings.services import JobQueueService

        payload = data or {}
        job = JobQueueService.enqueue(
            "recompute_accounting_balances",
            {
                "from_date": payload.get("from_date") or payload.get("startDate") or timezone.now().date().isoformat(),
                "to_date": payload.get("to_date") or payload.get("endDate") or timezone.now().date().isoformat(),
            },
            request=request,
        )
        return successResponse("Accounting balance recompute queued successfully.", data={"job_id": job.id})

    @staticmethod
    def jobHandlers():
        return {
            "accounting_reflection": lambda data, job: AccountingService.reflectTransactionFromRule(
                data.get("history_id") or data.get("transaction_history_id"),
                TransactionService.requestFromJob(job),
            ),
            "delete_accounting_reflection": lambda data, job: AccountingService.deleteTransactionReflection(
                data.get("history_id") or data.get("transaction_history_id"),
                TransactionService.requestFromJob(job),
            ),
            "record_refund_shipping_transaction": lambda data, job: AccountingService.recordRefundShipping(
                data.get("return_order_id") or data.get("refund_id") or data.get("order_refund_id"),
                TransactionService.requestFromJob(job),
            ),
            "prepare_transaction_history": lambda data, job: TransactionService.prepareTransactionHistory(
                data.get("transaction_id"),
                TransactionService.requestFromJob(job),
            ),
            "detect_scheduled_transactions": lambda data, job: TransactionService.detectScheduledTransactions(
                data,
                TransactionService.requestFromJob(job),
            ),
            "execute_delayed_transaction": lambda data, job: TransactionService.executeDelayedTransaction(
                data.get("history_id"),
                TransactionService.requestFromJob(job),
            ),
            "trigger_recurring_transactions": lambda data, job: TransactionService.triggerRecurringTransactions(
                data,
                TransactionService.requestFromJob(job),
            ),
            "recompute_accounting_balances": lambda data, job: AccountingService.recomputeBalances(
                data.get("from_date") or data.get("startDate"),
                data.get("to_date") or data.get("endDate"),
                TransactionService.requestFromJob(job),
            ),
        }
