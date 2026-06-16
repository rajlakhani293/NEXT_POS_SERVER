from django.contrib import admin

from apps.accounting.models import (
    Transaction,
    TransactionAccount,
    TransactionActionRule,
    TransactionBalanceDay,
    TransactionBalanceMonth,
    TransactionHistory,
)


@admin.register(TransactionAccount)
class TransactionAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "account", "category_identifier", "sub_category", "status", "company", "branch")
    list_filter = ("category_identifier", "status")
    search_fields = ("name", "account")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "value", "scheduled_date", "account", "recurring", "active", "status")
    list_filter = ("type", "recurring", "active", "status")
    search_fields = ("name", "description")


@admin.register(TransactionHistory)
class TransactionHistoryAdmin(admin.ModelAdmin):
    list_display = ("transaction", "transaction_account", "operation", "value", "type", "trigger_date", "status")
    list_filter = ("operation", "type", "status")


@admin.register(TransactionBalanceDay)
class TransactionBalanceDayAdmin(admin.ModelAdmin):
    list_display = ("date", "opening_balance", "income", "expense", "closing_balance", "status", "company", "branch")
    list_filter = ("date", "status")


@admin.register(TransactionBalanceMonth)
class TransactionBalanceMonthAdmin(admin.ModelAdmin):
    list_display = ("date", "opening_balance", "income", "expense", "closing_balance", "status", "company", "branch")
    list_filter = ("date", "status")


@admin.register(TransactionActionRule)
class TransactionActionRuleAdmin(admin.ModelAdmin):
    list_display = (
        "on",
        "action",
        "account",
        "do",
        "offset_account",
        "locked",
        "status",
        "company",
        "branch",
    )
    list_filter = ("on", "action", "do", "locked", "status")
