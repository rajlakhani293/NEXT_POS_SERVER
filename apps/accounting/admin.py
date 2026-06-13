from django.contrib import admin

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
    list_display = (
        "event_key",
        "action",
        "account",
        "offset_action",
        "offset_account",
        "status",
        "company",
        "branch",
    )
    list_filter = ("event_key", "action", "offset_action", "status")


@admin.register(AccountingSetting)
class AccountingSettingAdmin(admin.ModelAdmin):
    list_display = ("company", "branch", "sales_revenue_account", "order_cash_account")
