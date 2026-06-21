# type: ignore
import json
from apps.settings.models import Option


ORDER_TYPE_OPTIONS = [
    {"value": "takeaway", "label": "Take Order"},
    {"value": "delivery", "label": "Delivery"},
]


BUSINESS_SETTING_FIELDS = [
    "allow_partial_orders",
    "enable_customer_rewards",
    "enable_credit_account",
    "enable_cash_registers",
    "allow_decimal_quantities",
    "quick_product_enabled",
    "show_quantity",
    "currency_precision",
    "hide_empty_categories",
    "unit_price_editable",
    "default_change_payment_type",
    "order_types",
]


OPTION_KEY_MAP = {
    "allow_partial_orders": "orders_allow_partial",
    "enable_customer_rewards": "customers_rewards_enabled",
    "enable_credit_account": "customers_credit_enabled",
    "enable_cash_registers": "registers_enabled",
    "allow_decimal_quantities": "allow_decimal_quantities",
    "quick_product_enabled": "quick_product",
    "show_quantity": "show_quantity",
    "currency_precision": "currency_precision",
    "hide_empty_categories": "hide_empty_categories",
    "unit_price_editable": "unit_price_editable",
    "order_types": "order_types",
    "default_change_payment_type": "registers_default_change_payment_type",
}


STATIC_OPTION_DEFAULTS = {
    "registration_enabled": "no",
    "store_name": "POS",
    "store_language": "en",
    "allow_decimal_quantities": "yes",
    "quick_product": "yes",
    "show_quantity": "yes",
    "currency_precision": 2,
    "hide_empty_categories": "yes",
    "unit_price_editable": "yes",
    "order_types": ["takeaway", "delivery"],
    "scale_barcode_product_length": 4,
    "orders_code_type": "sequential",
    "orders_allow_unpaid": "no",
    "orders_allow_partial": "no",
    "orders_strict_instalments": "no",
    "orders_quotation_expiration": "never",
    "customers_rewards_enabled": "no",
    "customers_credit_enabled": "no",
    "registers_enabled": "no",
    "pos_preferred_price": "sale_price",
    "pos_vat": "disabled",
    "scale_barcode_enabled": "no",
    "scale_barcode_prefix": "2",
}


DYNAMIC_OPTION_DEFAULTS = [
    "registers_default_change_payment_type",
    "accounting_default_paid_expense_offset_account",
]


DEFAULT_ORDER_SETTINGS = [
    ("pos_preferred_price", "sale_price"),
    ("pos_vat", "disabled"),
    ("order_type", "takeaway"),
    ("discount_type", ""),
    ("discount_value", "0"),
    ("tax_type", ""),
    ("tax_group", ""),
    ("note_visibility", "hidden"),
]


DEFAULT_PAYMENT_TYPES = [
    {
        "identifier": "cash-payment",
        "label": "Cash",
        "description": "Default cash payment method.",
        "priority": 0,
    },
    {
        "identifier": "bank-payment",
        "label": "Bank Payment",
        "description": "Default bank payment method.",
        "priority": 1,
    },
    {
        "identifier": "account-payment",
        "label": "Customer Account",
        "description": "Default customer account payment method.",
        "priority": 2,
    },
]


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


DEFAULT_ACCOUNT_RULES = [
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


DEFAULT_SCALE_RANGES = [
    ("Test Range", 1, 99, 1, "Range for testing and development purposes"),
    ("Fruits & Vegetables", 100, 999, 100, "Fresh produce that requires weighing"),
    ("Meat & Poultry", 1000, 1999, 1000, "Fresh meat and poultry products"),
    ("Seafood", 2000, 2999, 2000, "Fresh fish and seafood products"),
    ("Bakery", 3000, 3999, 3000, "Bakery items sold by weight"),
    ("Deli & Cheese", 4000, 4999, 4000, "Deli meats and cheese products"),
    ("Bulk Foods", 5000, 5999, 5000, "Bulk food items like nuts, grains, and spices"),
    ("Prepared Foods", 6000, 6999, 6000, "Ready-to-eat prepared foods"),
    ("Organic Products", 7000, 7999, 7000, "Certified organic products"),
    ("Specialty Items", 8000, 8999, 8000, "Specialty and gourmet products"),
    ("General Weighable", 9000, 9999, 9000, "General category for weighable products"),
]


def defaultBusinessSettings():
    return {
        "allow_partial_orders": False,
        "enable_customer_rewards": False,
        "enable_credit_account": False,
        "enable_cash_registers": True,
        "allow_decimal_quantities": True,
        "quick_product_enabled": True,
        "show_quantity": True,
        "currency_precision": 2,
        "hide_empty_categories": True,
        "unit_price_editable": True,
        "default_change_payment_type": "cash-payment",
        "order_types": ["takeaway", "delivery"],
    }


def encodeOptionValue(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value), True
    if value is True:
        return "yes", False
    if value is False:
        return "no", False
    return str(value or ""), False


def decodeOptionValue(option):
    if option is None:
        return None
    if option.array:
        try:
            return json.loads(option.value or "[]")
        except (TypeError, json.JSONDecodeError):
            return []
    if option.value == "yes":
        return True
    if option.value == "no":
        return False
    if str(option.value or "").isdigit():
        return int(option.value)
    return option.value


def ensureOptionValue(company, branch, key, value, user=None):
    encoded_value, is_array = encodeOptionValue(value)
    option, _created = Option.objects.get_or_create(
        company=company,
        branch=branch,
        key=key,
        defaults={
            "user": user,
            "value": encoded_value,
            "array": is_array,
        },
    )
    update_fields = []
    if user and option.user_id is None:
        option.user = user
        update_fields.append("user")
    if option.value != encoded_value or option.array != is_array:
        option.value = encoded_value
        option.array = is_array
        update_fields.extend(["value", "array"])
    if update_fields:
        option.save(update_fields=[*set(update_fields), "updated_at"])
    return option


def defaultOptionRows(company, branch):
    from apps.settings.models import PaymentType
    from apps.accounting.models import TransactionAccount

    payment_type = PaymentType.objects.filter(
        company_id=company.id,
        branch_id=branch.id,
        identifier="cash-payment",
        status=0,
    ).first()
    expense_cash = TransactionAccount.objects.filter(
        company_id=company.id,
        branch_id=branch.id,
        account="1004-assets-expenses-cash",
        status=0,
    ).first()
    return {
        **STATIC_OPTION_DEFAULTS,
        "registers_default_change_payment_type": payment_type.id if payment_type else 1,
        "accounting_default_paid_expense_offset_account": expense_cash.id if expense_cash else "",
    }


def ensureDefaultOptions(company, branch, user=None):
    for key, value in defaultOptionRows(company, branch).items():
        ensureOptionValue(company, branch, key, value, user=user)
    return Option.objects.filter(company=company, branch=branch)


def ensureOrderSettings(sale_order, request):
    from apps.sales.models import OrderSetting

    sale_order.settings.all().delete()
    settings = []
    for key, value in DEFAULT_ORDER_SETTINGS:
        settings.append(
            OrderSetting(
                user=request.user,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                sale_order=sale_order,
                key=key,
                value=value,
            )
        )
    OrderSetting.objects.bulk_create(settings)
    return settings


def buildBusinessSettingsFromOptions(options):
    option_map = {option.key: option for option in options}
    defaults = defaultBusinessSettings()
    values = {
        "allow_partial_orders": defaults["allow_partial_orders"],
        "enable_customer_rewards": defaults["enable_customer_rewards"],
        "enable_credit_account": defaults["enable_credit_account"],
        "enable_cash_registers": defaults["enable_cash_registers"],
    }
    reverse_map = {
        key: decodeOptionValue(option_map.get(option_key))
        for key, option_key in OPTION_KEY_MAP.items()
    }
    values.update({key: value for key, value in reverse_map.items() if value is not None})
    return {**defaults, **values}


class TenantDefaultsService:
    @staticmethod
    def ensureBranchDefaults(company, branch):
        from apps.accounting.services import AccountingService
        from apps.accounts.services import AccountsService
        from apps.catalog.services import ScaleRangeService
        from apps.settings.services import PaymentTypeService

        AccountsService.seedDefaultRoles(company, branch)
        PaymentTypeService.ensureDefaultPaymentTypes(company, branch)
        AccountingService.ensureDefaultAccounting(company, branch)
        ensureDefaultOptions(company=company, branch=branch)
        ScaleRangeService.ensureDefaultScaleRanges(company, branch)
