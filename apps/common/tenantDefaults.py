# type: ignore
import json
from apps.settings.models import Option


ORDER_TYPE_OPTIONS = [
    {"value": "takeaway", "label": "Take Order"},
    {"value": "delivery", "label": "Delivery"},
]


BUSINESS_SETTING_FIELDS = [
    "enable_customer_rewards",
    "enable_credit_account",
    "enable_cash_registers",
    "allow_decimal_quantities",
    "quick_product_enabled",
    "show_quantity",
    "items_merge",
    "force_autofocus",
    "enable_pinned_products",
    "show_preview_pinned_products",
    "hide_exhausted_products",
    "allow_wholesale_price",
    "pos_numpad",
    "pos_idle_counter",
    "pos_disbursement",
    "pos_action_permission_enabled",
    "pos_action_permission_duration",
    "pos_action_permission_restricted_features",
    "pos_action_permission_cooldown_features",
    "pos_keyboard_cancel_order",
    "pos_keyboard_hold_order",
    "pos_keyboard_create_customer",
    "pos_keyboard_payment",
    "pos_keyboard_shipping",
    "pos_keyboard_note",
    "pos_keyboard_order_type",
    "pos_keyboard_fullscreen",
    "pos_keyboard_quick_search",
    "pos_keyboard_toggle_merge",
    "pos_amount_shortcut",
    "customers_default",
    "customers_default_group",
    "pos_layout",
    "pos_sound_enabled",
    "currency_symbol",
    "currency_iso",
    "currency_position",
    "currency_preferred",
    "currency_thousand_separator",
    "currency_decimal_separator",
    "currency_precision",
    "hide_empty_categories",
    "unit_price_editable",
    "default_change_payment_type",
    "pos_registers_default_change_payment_type",
    "order_types",
    "pos_quick_product_default_unit",
    "pos_preferred_price",
    "pos_enable_reordering",
    "pos_vat",
    "store_language",
    "registration_enabled",
    "registration_role",
    "registration_validated",
    "recovery_enabled",
    "date_format",
    "datetime_format",
    "datetime_timezone",
    "scale_barcode_enabled",
    "scale_barcode_prefix",
    "scale_barcode_product_length",
    "scale_barcode_value_length",
    "scale_barcode_type",
    "orders_code_type",
    "orders_allow_unpaid",
    "orders_allow_partial",
    "orders_strict_instalments",
    "orders_quotation_expiration",
    "pos_tax_group",
    "pos_tax_type",
    "printing_document",
    "printing_enabled_for",
    "printing_gateway",
    "pos_complete_sale_audio",
    "pos_new_item_audio",
    "pos_order_sms",
    "invoice_receipt_template",
    "invoice_receipt_logo",
    "invoice_merge_similar_products",
    "invoice_display_tax_breakdown",
    "invoice_receipt_footer",
    "invoice_receipt_column_a",
    "invoice_receipt_column_b",
    "reports_email",
    "accounting_expenses_accounts",
    "accounting_default_paid_expense_offset_account",
    "accounting_orders_revenues_account",
    "accounting_orders_cash_account",
    "accounting_orders_unpaid_account",
    "accounting_orders_cogs_account",
]


OPTION_KEY_MAP = {
    "orders_allow_partial": "orders_allow_partial",
    "enable_customer_rewards": "customers_rewards_enabled",
    "enable_credit_account": "customers_credit_enabled",
    "enable_cash_registers": "registers_enabled",
    "allow_decimal_quantities": "allow_decimal_quantities",
    "quick_product_enabled": "quick_product",
    "show_quantity": "show_quantity",
    "items_merge": "items_merge",
    "force_autofocus": "force_autofocus",
    "enable_pinned_products": "enable_pinned_products",
    "show_preview_pinned_products": "show_preview_pinned_products",
    "hide_exhausted_products": "hide_exhausted_products",
    "allow_wholesale_price": "allow_wholesale_price",
    "pos_numpad": "pos_numpad",
    "pos_idle_counter": "pos_idle_counter",
    "pos_disbursement": "pos_disbursement",
    "pos_action_permission_enabled": "pos_action_permission_enabled",
    "pos_action_permission_duration": "pos_action_permission_duration",
    "pos_action_permission_restricted_features": "pos_action_permission_restricted_features",
    "pos_action_permission_cooldown_features": "pos_action_permission_cooldown_features",
    "pos_keyboard_cancel_order": "pos_keyboard_cancel_order",
    "pos_keyboard_hold_order": "pos_keyboard_hold_order",
    "pos_keyboard_create_customer": "pos_keyboard_create_customer",
    "pos_keyboard_payment": "pos_keyboard_payment",
    "pos_keyboard_shipping": "pos_keyboard_shipping",
    "pos_keyboard_note": "pos_keyboard_note",
    "pos_keyboard_order_type": "pos_keyboard_order_type",
    "pos_keyboard_fullscreen": "pos_keyboard_fullscreen",
    "pos_keyboard_quick_search": "pos_keyboard_quick_search",
    "pos_keyboard_toggle_merge": "pos_keyboard_toggle_merge",
    "pos_amount_shortcut": "pos_amount_shortcut",
    "customers_default": "customers_default",
    "customers_default_group": "customers_default_group",
    "pos_layout": "pos_layout",
    "pos_sound_enabled": "pos_sound_enabled",
    "currency_symbol": "currency_symbol",
    "currency_iso": "currency_iso",
    "currency_position": "currency_position",
    "currency_preferred": "currency_preferred",
    "currency_thousand_separator": "currency_thousand_separator",
    "currency_decimal_separator": "currency_decimal_separator",
    "currency_precision": "currency_precision",
    "hide_empty_categories": "hide_empty_categories",
    "unit_price_editable": "unit_price_editable",
    "order_types": "order_types",
    "default_change_payment_type": "registers_default_change_payment_type",
    "pos_registers_default_change_payment_type": "registers_default_change_payment_type",
    "pos_preferred_price": "pos_preferred_price",
    "pos_quick_product_default_unit": "quick_product_default_unit",
    "pos_enable_reordering": "enable_reordering",
    "pos_vat": "pos_vat",
    "store_language": "store_language",
    "registration_enabled": "registration_enabled",
    "registration_role": "registration_role",
    "registration_validated": "registration_validated",
    "recovery_enabled": "recovery_enabled",
    "date_format": "date_format",
    "datetime_format": "datetime_format",
    "datetime_timezone": "datetime_timezone",
    "scale_barcode_enabled": "scale_barcode_enabled",
    "scale_barcode_prefix": "scale_barcode_prefix",
    "scale_barcode_product_length": "scale_barcode_product_length",
    "scale_barcode_value_length": "scale_barcode_value_length",
    "scale_barcode_type": "scale_barcode_type",
    "orders_code_type": "orders_code_type",
    "orders_allow_unpaid": "orders_allow_unpaid",
    "orders_strict_instalments": "orders_strict_instalments",
    "orders_quotation_expiration": "orders_quotation_expiration",
    "pos_tax_group": "pos_tax_group",
    "pos_tax_type": "pos_tax_type",
    "printing_document": "pos_printing_document",
    "printing_enabled_for": "pos_printing_enabled_for",
    "printing_gateway": "pos_printing_gateway",
    "pos_complete_sale_audio": "pos_complete_sale_audio",
    "pos_new_item_audio": "pos_new_item_audio",
    "pos_order_sms": "pos_order_sms",
    "invoice_receipt_template": "invoice_receipt_template",
    "invoice_receipt_logo": "invoice_receipt_logo",
    "invoice_merge_similar_products": "invoice_merge_similar_products",
    "invoice_display_tax_breakdown": "invoice_display_tax_breakdown",
    "invoice_receipt_footer": "invoice_receipt_footer",
    "invoice_receipt_column_a": "invoice_receipt_column_a",
    "invoice_receipt_column_b": "invoice_receipt_column_b",
    "reports_email": "reports_email",
    "accounting_expenses_accounts": "accounting_expenses_accounts",
    "accounting_default_paid_expense_offset_account": "accounting_default_paid_expense_offset_account",
    "accounting_orders_revenues_account": "accounting_orders_revenues_account",
    "accounting_orders_cash_account": "accounting_orders_cash_account",
    "accounting_orders_unpaid_account": "accounting_orders_unpaid_account",
    "accounting_orders_cogs_account": "accounting_orders_cogs_account",
}


STATIC_OPTION_DEFAULTS = {
    "registration_enabled": "no",
    "registration_role": "",
    "registration_validated": "no",
    "recovery_enabled": "yes",
    "date_format": "Y-m-d",
    "datetime_format": "Y-m-d H:i",
    "datetime_timezone": "UTC",
    "store_language": "en",
    "allow_decimal_quantities": "yes",
    "quick_product": "yes",
    "show_quantity": "yes",
    "items_merge": "yes",
    "force_autofocus": "no",
    "enable_pinned_products": "no",
    "show_preview_pinned_products": "no",
    "hide_exhausted_products": "no",
    "allow_wholesale_price": "no",
    "pos_numpad": "default",
    "pos_idle_counter": "disabled",
    "pos_disbursement": "no",
    "pos_action_permission_enabled": "no",
    "pos_action_permission_duration": "5",
    "pos_action_permission_restricted_features": [],
    "pos_action_permission_cooldown_features": "5",
    "pos_keyboard_cancel_order": [],
    "pos_keyboard_hold_order": [],
    "pos_keyboard_create_customer": [],
    "pos_keyboard_payment": [],
    "pos_keyboard_shipping": [],
    "pos_keyboard_note": [],
    "pos_keyboard_order_type": [],
    "pos_keyboard_fullscreen": [],
    "pos_keyboard_quick_search": [],
    "pos_keyboard_toggle_merge": [],
    "pos_amount_shortcut": "",
    "customers_default": "",
    "customers_default_group": "",
    "pos_layout": "grocery_shop",
    "pos_sound_enabled": "yes",
    "currency_symbol": "₹",
    "currency_iso": "INR",
    "currency_position": "before",
    "currency_preferred": "symbol",
    "currency_thousand_separator": ",",
    "currency_decimal_separator": ".",
    "currency_precision": 2,
    "hide_empty_categories": "yes",
    "unit_price_editable": "yes",
    "order_types": ["takeaway", "delivery"],
    "scale_barcode_product_length": 5,
    "scale_barcode_value_length": 5,
    "scale_barcode_type": "weight",
    "orders_code_type": "date_sequential",
    "orders_allow_unpaid": "yes",
    "orders_allow_partial": "no",
    "orders_strict_instalments": "no",
    "orders_quotation_expiration": "never",
    "customers_rewards_enabled": "no",
    "customers_credit_enabled": "no",
    "registers_enabled": "no",
    "registers_default_change_payment_type": "",
    "pos_preferred_price": "net_prices",
    "quick_product_default_unit": "",
    "enable_reordering": "no",
    "pos_vat": "disabled",
    "pos_tax_group": "",
    "pos_tax_type": "",
    "scale_barcode_enabled": "no",
    "scale_barcode_prefix": "2",
    "pos_printing_document": "receipt",
    "pos_printing_enabled_for": "only_paid_orders",
    "pos_printing_gateway": "default",
    "pos_complete_sale_audio": "",
    "pos_new_item_audio": "",
    "pos_order_sms": "no",
    "invoice_receipt_template": "default",
    "invoice_receipt_logo": "",
    "invoice_merge_similar_products": "no",
    "invoice_display_tax_breakdown": "no",
    "invoice_receipt_footer": "",
    "invoice_receipt_column_a": "",
    "invoice_receipt_column_b": "",
    "reports_email": "no",
    "accounting_expenses_accounts": [],
    "accounting_default_paid_expense_offset_account": "",
    "accounting_orders_revenues_account": "",
    "accounting_orders_cash_account": "",
    "accounting_orders_unpaid_account": "",
    "accounting_orders_cogs_account": "",
}


DYNAMIC_OPTION_DEFAULTS = [
    "registers_default_change_payment_type",
    "accounting_default_paid_expense_offset_account",
]


DEFAULT_ORDER_SETTINGS = [
    ("pos_preferred_price", "net_prices"),
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
        "orders_allow_partial": False,
        "enable_customer_rewards": False,
        "enable_credit_account": False,
        "enable_cash_registers": True,
        "allow_decimal_quantities": True,
        "quick_product_enabled": True,
        "show_quantity": True,
        "items_merge": True,
        "force_autofocus": False,
        "enable_pinned_products": False,
        "show_preview_pinned_products": False,
        "hide_exhausted_products": False,
        "allow_wholesale_price": False,
        "pos_numpad": "default",
        "pos_idle_counter": "disabled",
        "pos_disbursement": "no",
        "pos_action_permission_enabled": "no",
        "pos_action_permission_duration": "5",
        "pos_action_permission_restricted_features": [],
        "pos_action_permission_cooldown_features": "5",
        "pos_keyboard_cancel_order": [],
        "pos_keyboard_hold_order": [],
        "pos_keyboard_create_customer": [],
        "pos_keyboard_payment": [],
        "pos_keyboard_shipping": [],
        "pos_keyboard_note": [],
        "pos_keyboard_order_type": [],
        "pos_keyboard_fullscreen": [],
        "pos_keyboard_quick_search": [],
        "pos_keyboard_toggle_merge": [],
        "pos_amount_shortcut": "",
        "customers_default": "",
        "customers_default_group": "",
        "pos_layout": "grocery_shop",
        "pos_sound_enabled": "yes",
        "currency_symbol": "₹",
        "currency_iso": "INR",
        "currency_position": "before",
        "currency_preferred": "symbol",
        "currency_thousand_separator": ",",
        "currency_decimal_separator": ".",
        "currency_precision": 2,
        "hide_empty_categories": True,
        "unit_price_editable": True,
        "default_change_payment_type": "cash-payment",
        "pos_registers_default_change_payment_type": "cash-payment",
        "order_types": ["takeaway", "delivery"],
        "pos_quick_product_default_unit": "",
        "pos_preferred_price": "net_prices",
        "pos_enable_reordering": False,
        "pos_vat": "disabled",
        "registration_enabled": "no",
        "registration_role": "",
        "registration_validated": "no",
        "recovery_enabled": "yes",
        "date_format": "Y-m-d",
        "datetime_format": "Y-m-d H:i",
        "datetime_timezone": "UTC",
        "scale_barcode_enabled": False,
        "scale_barcode_prefix": "2",
        "scale_barcode_product_length": 5,
        "scale_barcode_value_length": 5,
        "scale_barcode_type": "weight",
        "orders_code_type": "date_sequential",
        "orders_allow_unpaid": True,
        "orders_strict_instalments": False,
        "orders_quotation_expiration": "never",
        "pos_tax_group": "",
        "pos_tax_type": "",
        "printing_document": "receipt",
        "printing_enabled_for": "only_paid_orders",
        "printing_gateway": "default",
        "pos_complete_sale_audio": "",
        "pos_new_item_audio": "",
        "pos_order_sms": "no",
        "invoice_receipt_template": "default",
        "invoice_receipt_logo": "",
        "invoice_merge_similar_products": False,
        "invoice_display_tax_breakdown": False,
        "invoice_receipt_footer": "",
        "invoice_receipt_column_a": "",
        "invoice_receipt_column_b": "",
        "reports_email": "no",
        "accounting_expenses_accounts": [],
        "accounting_default_paid_expense_offset_account": "",
        "accounting_orders_revenues_account": "",
        "accounting_orders_cash_account": "",
        "accounting_orders_unpaid_account": "",
        "accounting_orders_cogs_account": "",
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


def ensureOptionValue(company, branch, key, value, user=None, overwrite=True):
    from apps.common.commonQuery import commonQuery

    encoded_value, is_array = encodeOptionValue(value)
    option, _created = commonQuery.getOrCreateRecord(
        Option,
        {
            "company": company,
            "branch": branch,
            "key": key,
        },
        defaults={
            "user": user,
            "value": encoded_value,
            "array": is_array,
        },
        tenant_config={},
        return_plain=False,
    )
    update_fields = []
    if user and option.user_id is None:
        option.user = user
        update_fields.append("user")
    should_update_value = overwrite or option.value in [None, ""]
    if should_update_value and (option.value != encoded_value or option.array != is_array):
        option.value = encoded_value
        option.array = is_array
        update_fields.extend(["value", "array"])
    if update_fields:
        option.save(update_fields=[*set(update_fields), "updated_at"])
    return option


def defaultOptionRows(company, branch):
    from apps.settings.models import PaymentType
    from apps.accounting.models import TransactionAccount
    from apps.common.commonQuery import commonQuery

    payment_type = commonQuery.findOneRecord(
        PaymentType,
        {
            "company_id": company.id,
            "branch_id": branch.id,
            "identifier": "cash-payment",
            "status": 0,
        },
        tenant_config={},
    )
    expense_cash = commonQuery.findOneRecord(
        TransactionAccount,
        {
            "company_id": company.id,
            "branch_id": branch.id,
            "account": "1004-assets-expenses-cash",
            "status": 0,
        },
        tenant_config={},
    )
    return {
        **STATIC_OPTION_DEFAULTS,
        "registers_default_change_payment_type": payment_type["id"] if payment_type else 1,
        "accounting_default_paid_expense_offset_account": expense_cash["id"] if expense_cash else "",
    }


def ensureDefaultOptions(company, branch, user=None):
    from apps.common.commonQuery import commonQuery

    for key, value in defaultOptionRows(company, branch).items():
        ensureOptionValue(company, branch, key, value, user=user, overwrite=False)
    return commonQuery.scopedQueryset(Option, {"company": company, "branch": branch}, tenant_config={})


def ensureOrderSettings(sale_order, request):
    from apps.sales.models import OrderSetting
    from apps.common.commonQuery import commonQuery

    commonQuery.branchScopedQueryset(OrderSetting, {"sale_order": sale_order}, request).delete()
    option_keys = [
        key
        for key, _default_value in DEFAULT_ORDER_SETTINGS
        if key not in ["order_type", "discount_type", "discount_value", "tax_type", "tax_group", "note_visibility"]
    ]
    option_values = {
        option.key: option.value
        for option in commonQuery.branchScopedQueryset(
            Option,
            {"status": 0, "key__in": option_keys},
            request,
        )
    }
    order_values = {
        "order_type": getattr(sale_order, "order_type", None) or getattr(sale_order, "type", None) or "takeaway",
        "discount_type": getattr(sale_order, "discount_type", None) or "",
        "discount_value": str(getattr(sale_order, "discount_percentage", None) or getattr(sale_order, "discount_amount", None) or 0),
        "tax_type": getattr(sale_order, "tax_type", None) or "",
        "tax_group": str(getattr(sale_order, "tax_group_id", None) or ""),
        "note_visibility": getattr(sale_order, "note_visibility", None) or "hidden",
    }
    settings = []
    for key, value in DEFAULT_ORDER_SETTINGS:
        settings.append(
            {
                "sale_order": sale_order,
                "key": key,
                "value": order_values[key] if key in order_values else option_values.get(key, value),
            }
        )
    commonQuery.bulkCreate(OrderSetting, settings, request=request, tenant_config=True)
    return settings


def buildBusinessSettingsFromOptions(options):
    option_map = {option.key: option for option in options}
    defaults = defaultBusinessSettings()
    values = {
        "orders_allow_partial": defaults["orders_allow_partial"],
        "enable_customer_rewards": defaults["enable_customer_rewards"],
        "enable_credit_account": defaults["enable_credit_account"],
        "enable_cash_registers": defaults["enable_cash_registers"],
    }
    reverse_map = {
        key: decodeOptionValue(option_map.get(option_key))
        for key, option_key in OPTION_KEY_MAP.items()
    }
    values.update({key: value for key, value in reverse_map.items() if value is not None})
    merged = {**defaults, **values}
    if merged.get("orders_code_type") == "sequential":
        merged["orders_code_type"] = "date_sequential"
    merged["allow_partial_orders"] = merged["orders_allow_partial"]
    return merged


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
