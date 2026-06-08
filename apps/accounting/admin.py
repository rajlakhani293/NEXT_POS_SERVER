from django.contrib import admin

from apps.accounting.models import (
    ActiveTransactionHistory,
    Transaction,
    TransactionAccount,
    TransactionActionRule,
    TransactionBalanceDay,
    TransactionBalanceMonth,
    TransactionHistory,
)


@admin.register(TransactionAccount)
class TransactionAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "account_type", "current_balance", "status", "company", "branch")
    list_filter = ("account_type", "status")
    search_fields = ("name", "code")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("name", "transaction_type", "source_type", "value", "transaction_date", "account", "status")
    list_filter = ("transaction_type", "source_type", "status")
    search_fields = ("name", "reference_number")


@admin.register(TransactionHistory)
class TransactionHistoryAdmin(admin.ModelAdmin):
    list_display = ("transaction", "account", "action_type", "amount", "balance_before", "balance_after", "status")
    list_filter = ("action_type", "source_type", "status")


@admin.register(ActiveTransactionHistory)
class ActiveTransactionHistoryAdmin(admin.ModelAdmin):
    list_display = ("transaction", "account", "action_type", "amount", "source_type", "status")
    list_filter = ("action_type", "source_type", "status")


@admin.register(TransactionBalanceDay)
class TransactionBalanceDayAdmin(admin.ModelAdmin):
    list_display = ("account", "balance_date", "opening_balance", "total_credit", "total_debit", "closing_balance", "status")
    list_filter = ("balance_date", "status")


@admin.register(TransactionBalanceMonth)
class TransactionBalanceMonthAdmin(admin.ModelAdmin):
    list_display = ("account", "year", "month", "opening_balance", "total_credit", "total_debit", "closing_balance", "status")
    list_filter = ("year", "month", "status")


@admin.register(TransactionActionRule)
class TransactionActionRuleAdmin(admin.ModelAdmin):
    list_display = ("source_type", "action_name", "debit_account", "credit_account", "is_system", "status")
    list_filter = ("source_type", "is_system", "status")
