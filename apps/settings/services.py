# type: ignore
import datetime
import json
import re
import time
import zoneinfo
from pathlib import Path
from types import SimpleNamespace
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db import connection
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import Role, User
from apps.accounting.models import TransactionAccount
from apps.catalog.models import TaxGroup, Unit
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import jsonsafe, serializeModelInstance, validateUniqueFields
from apps.common.responses import successResponse
from apps.common.tenantDefaults import (
    BUSINESS_SETTING_FIELDS,
    DEFAULT_PAYMENT_TYPES,
    OPTION_KEY_MAP,
    ORDER_TYPE_OPTIONS,
    buildBusinessSettingsFromOptions,
    decodeOptionValue,
    defaultBusinessSettings,
    ensureDefaultOptions,
    ensureOptionValue,
)
from apps.organizations.models import Branch
from apps.customers.models import Customer, CustomerGroup
from apps.settings.models import FailedJob, Job, Media, Notification, PaymentType, paymentTypeValues


class OptionSettingService:
    OPTION_KEY_MAP = OPTION_KEY_MAP
    STRING_SETTING_FIELDS = {
        "currency_symbol",
        "currency_iso",
        "currency_position",
        "currency_preferred",
        "currency_thousand_separator",
        "currency_decimal_separator",
        "default_change_payment_type",
        "pos_preferred_price",
        "pos_vat",
        "store_language",
        "registration_enabled",
        "registration_role",
        "registration_validated",
        "date_format",
        "datetime_format",
        "datetime_timezone",
        "scale_barcode_prefix",
        "scale_barcode_type",
        "orders_code_type",
        "orders_quotation_expiration",
        "pos_tax_group",
        "pos_tax_type",
        "pos_numpad",
        "pos_idle_counter",
        "pos_disbursement",
        "pos_action_permission_duration",
        "pos_action_permission_cooldown_features",
        "pos_amount_shortcut",
        "pos_printing_document",
        "pos_printing_enabled_for",
        "pos_printing_gateway",
        "reports_email",
    }
    INTEGER_SETTING_FIELDS = {
        "currency_precision",
        "scale_barcode_product_length",
        "scale_barcode_value_length",
    }
    SOURCE_OPTION_ALIASES = {
        "currency_prefered": "currency_preferred",
        "pos_prefered_price": "pos_preferred_price",
        "pos_unit_price_ediable": "unit_price_editable",
        "pos_allow_decimal_quantities": "allow_decimal_quantities",
        "pos_quick_product": "quick_product",
        "pos_show_quantity": "show_quantity",
        "pos_items_merge": "items_merge",
        "pos_allow_wholesale_price": "allow_wholesale_price",
        "pos_hide_empty_categories": "hide_empty_categories",
        "pos_force_autofocus": "force_autofocus",
        "pos_hide_exhausted_products": "hide_exhausted_products",
        "pos_enable_pinned_products": "enable_pinned_products",
        "pos_show_preview_pinned_products": "show_preview_pinned_products",
        "pos_order_types": "order_types",
        "pos_registers_enabled": "registers_enabled",
        "pos_registers_default_change_payment_type": "registers_default_change_payment_type",
        "customers_rewards_enabled": "customers_rewards_enabled",
        "customers_credit_enabled": "customers_credit_enabled",
        "orders_allow_partial": "orders_allow_partial",
    }
    SETTING_FORMS = {
        "general": {
            "title": "General Settings",
            "description": "Configure the general settings of the application.",
            "tabs": {
                "identification": [
                    ("store_language", "select", "Language", ""),
                    ("default_theme", "select", "Theme", ""),
                ],
                "currency": [
                    ("currency_symbol", "text", "Currency Symbol", "required"),
                    ("currency_iso", "text", "Currency ISO", "required"),
                    ("currency_position", "select", "Currency Position", ""),
                    ("currency_prefered", "select", "Preferred Currency", ""),
                    ("currency_thousand_separator", "text", "Currency Thousand Separator", ""),
                    ("currency_decimal_separator", "text", "Currency Decimal Separator", ""),
                    ("currency_precision", "select", "Currency Precision", ""),
                ],
                "date": [
                    ("date_format", "select", "Date Format", "", 'This define how the date should be defined. The default format is "Y-m-d".'),
                    ("datetime_format", "select", "Date Time Format", "", 'This define how the date and times should be formated. The default format is "Y-m-d H:i".'),
                    ("datetime_timezone", "select", "Timezone", "", "Determine the default timezone of the store."),
                ],
                "registration": [
                    ("registration_enabled", "select", "Registration", ""),
                    ("registration_role", "select", "Default Role", ""),
                    ("registration_validated", "select", "Validate Registration", ""),
                    ("recovery_enabled", "switch", "Password Recovery", ""),
                ],
            },
        },
        "orders": {
            "title": "Orders Settings",
            "description": "configure settings that applies to orders.",
            "tabs": {
                "general": [
                    ("orders_code_type", "select", "Order Code Type", "", "Determine how the system will generate code for each orders."),
                    ("orders_allow_unpaid", "switch", "Allow Unpaid Orders", "", 'Will prevent incomplete orders to be placed. If credit is allowed, this option should be set to "yes".'),
                    ("orders_allow_partial", "switch", "Allow Partial Orders", "", "Will prevent partially paid orders to be placed."),
                    ("orders_strict_instalments", "switch", "Strict Instalments", "", "Will enforce instalment to be paid on specific date."),
                    ("orders_quotation_expiration", "select", "Quotation Expiration", "", "Quotations will get deleted after they defined they has reached."),
                ],
            },
        },
        "customers": {
            "title": "Customers Settings",
            "description": "Configure the customers settings of the application.",
            "tabs": {
                "general": [
                    ("customers_rewards_enabled", "select", "Enable Reward", ""),
                    ("customers_default", "search-select", "Default Customer Account", ""),
                    ("customers_default_group", "select", "Default Customer Group", ""),
                    ("customers_credit_enabled", "select", "Enable Credit & Account", ""),
                ],
            },
        },
        "pos": {
            "title": "POS Settings",
            "description": "Configure the pos settings.",
            "tabs": {
                "layout": [
                    ("pos_layout", "select", "Layout", ""),
                    ("pos_complete_sale_audio", "select", "Sale Complete Sound", ""),
                    ("pos_new_item_audio", "select", "New Item Audio", ""),
                ],
                "printing": [
                    ("pos_printing_document", "select", "Printed Document", ""),
                    ("pos_printing_enabled_for", "select", "Printing Enabled For", ""),
                    ("pos_printing_gateway", "select", "Printing Gateway", ""),
                ],
                "registers": [
                    ("pos_registers_enabled", "select", "Enable Cash Registers", ""),
                    ("pos_idle_counter", "select", "Cashier Idle Counter", ""),
                    ("pos_disbursement", "select", "Cash Disbursement", ""),
                    ("pos_registers_default_change_payment_type", "select", "Default Change Payment Type", "required", "Define the payment type that will be used for all change from the registers."),
                ],
                "vat": [
                    ("pos_vat", "select", "VAT", ""),
                    ("pos_tax_group", "select", "Tax Group", ""),
                    ("pos_tax_type", "select", "Tax Type", ""),
                ],
                "pos_actions": [
                    ("pos_action_permission_duration", "select", "Permission Duration", ""),
                    ("pos_action_permission_restricted_features", "multiselect", "Restricted Features", ""),
                    ("pos_action_permission_cooldown_features", "select", "Cooldown Before New Request", ""),
                ],
                "scale-barcode": [
                    ("scale_barcode_prefix", "text", "Barcode Prefix", ""),
                    ("scale_barcode_type", "select", "Barcode Type", ""),
                    ("scale_barcode_product_length", "number", "Product Code Length", ""),
                    ("scale_barcode_value_length", "number", "Value Length", ""),
                ],
                "shortcuts": [
                    ("pos_keyboard_cancel_order", "inline-multiselect", "Cancel Order", ""),
                    ("pos_keyboard_hold_order", "inline-multiselect", "Hold Order", ""),
                    ("pos_keyboard_create_customer", "inline-multiselect", "Create Customer", ""),
                    ("pos_keyboard_payment", "inline-multiselect", "Proceed Payment", ""),
                    ("pos_keyboard_shipping", "inline-multiselect", "Open Shipping", ""),
                    ("pos_keyboard_note", "inline-multiselect", "Open Note", ""),
                    ("pos_keyboard_order_type", "inline-multiselect", "Order Type Selector", ""),
                    ("pos_keyboard_fullscreen", "inline-multiselect", "Toggle Fullscreen", ""),
                    ("pos_keyboard_quick_search", "inline-multiselect", "Quick Search", ""),
                    ("pos_keyboard_toggle_merge", "inline-multiselect", "Toggle Product Merge", ""),
                    ("pos_amount_shortcut", "text", "Amount Shortcuts", ""),
                ],
                 "features": [
                    ("pos_show_quantity", "switch", "Show Quantity", ""),
                    ("pos_items_merge", "switch", "Merge Similar Items", ""),
                    ("pos_allow_wholesale_price", "switch", "Allow Wholesale Price", ""),
                    ("pos_allow_decimal_quantities", "switch", "Decimal Quantities", ""),
                    ("pos_quick_product", "switch", "Quick Product", ""),
                    ("pos_quick_product_default_unit", "select", "Quick Product Default Unit", ""),
                    ("pos_unit_price_ediable", "switch", "Unit Price Editable", ""),
                    ("pos_prefered_price", "select", "Prefered Price", ""),
                    ("pos_order_types", "multiselect", "Order Types", ""),
                    ("pos_numpad", "select", "Numpad", ""),
                    ("pos_force_autofocus", "switch", "Force Autofocus", ""),
                    ("pos_hide_exhausted_products", "switch", "Hide Exhausted Products", ""),
                    ("pos_hide_empty_categories", "switch", "Hide Empty Category", ""),
                    ("pos_action_permission_enabled", "switch", "Action Permission", ""),
                    ("scale_barcode_enabled", "switch", "Scale Barcode", ""),
                    ("pos_enable_reordering", "switch", "Enable Reordering", ""),
                    ("pos_enable_pinned_products", "switch", "Pinned Products", ""),
                    ("pos_show_preview_pinned_products", "switch", "Pinned Product Preview", ""),
                ],
            },
        },
        "reports": {
            "title": "Reports Settings",
            "description": "Configure report delivery settings.",
            "tabs": {"general": [("reports_email", "switch", "Enable Email Reporting", "")]},
        },
        "invoices": {
            "title": "Invoice Settings",
            "description": "Configure how invoice and receipts are used.",
            "tabs": {
                "receipts": [
                    ("invoice_receipt_template", "select", "Receipt Template", ""),
                    ("invoice_receipt_logo", "media", "Receipt Logo", "", "Provide a URL to the logo."),
                    ("invoice_merge_similar_products", "switch", "Merge Similar Products", ""),
                    ("invoice_display_tax_breakdown", "switch", "Display Tax Breakdown", ""),
                    ("invoice_receipt_footer", "textarea", "Receipt Footer", ""),
                    ("invoice_receipt_column_a", "textarea", "Receipt Column A", ""),
                    ("invoice_receipt_column_b", "textarea", "Receipt Column B", ""),
                ],
            },
        },
        "accounting": {
            "title": "Accounting Settings",
            "description": "Configure accounting settings.",
            "tabs": {
                "general": [
                    ("accounting_expenses_accounts", "multiselect", "Expense Accounts", ""),
                    ("accounting_default_paid_expense_offset_account", "search-select", "Paid Expense Offset", ""),
                ],
            },
        },
        "reset": {
            "title": "Reset",
            "description": "Reset application data.",
            "tabs": {
                "reset": [
                    ("mode", "select", "Mode", "required"),
                    ("create_sales", "checkbox", "Create Sales (needs Procurements)", ""),
                    ("create_procurements", "checkbox", "Create Procurements", ""),
                ],
            },
        },
        "about": {
            "title": "About",
            "description": "Application information.",
            "tabs": {},
        },
    }

    ACCOUNT_OPTION_CATEGORIES = {
        "accounting_expenses_accounts": "expenses",
        "accounting_default_paid_expense_offset_account": "assets",
        "accounting_orders_revenues_account": "revenues",
        "accounting_orders_cash_account": "assets",
        "accounting_orders_unpaid_account": "assets",
        "accounting_orders_cogs_account": "expenses",
    }
    DATE_FORMAT_OPTIONS = [
        "Y-m-d",
        "Y/m/d",
        "d-m-y",
        "d/m/y",
        "M dS, Y",
        "d M Y",
        "d.m.Y",
    ]
    DATETIME_FORMAT_OPTIONS = [
        "Y-m-d H:i",
        "Y/m/d H:i",
        "d-m-y H:i",
        "d/m/y H:i",
        "M dS, Y H:i",
        "d M Y, H:i",
        "d.m.Y, H:i",
    ]
    YES_NO_OPTIONS = [
        ("yes", "Yes"),
        ("no", "No"),
    ]
    STATIC_FIELD_OPTIONS = {
        "default_theme": [
            ("light", "Light"),
            ("dark", "Dark"),
            ("phosphor", "Phosphor"),
        ],
        "currency_position": [
            ("before", "Before the amount"),
            ("after", "After the amount"),
        ],
        "currency_prefered": [
            ("iso", "ISO Currency"),
            ("symbol", "Symbol"),
        ],
        "currency_precision": [(str(index), f"{index} numbers after the decimal") for index in range(0, 6)],
        "registration_enabled": YES_NO_OPTIONS,
        "registration_validated": YES_NO_OPTIONS,
        "orders_code_type": [
            ("date_sequential", "Sequential"),
            ("random_code", "Random Code"),
            ("number_sequential", "Number Sequential"),
        ],
        "orders_allow_unpaid": YES_NO_OPTIONS,
        "orders_allow_partial": YES_NO_OPTIONS,
        "orders_strict_instalments": YES_NO_OPTIONS,
        "orders_quotation_expiration": [
            ("never", "Never"),
            ("3", "3 Days"),
            ("5", "5 Days"),
            ("10", "10 Days"),
            ("15", "15 Days"),
            ("30", "30 Days"),
        ],
        "customers_rewards_enabled": YES_NO_OPTIONS,
        "customers_force_valid_email": YES_NO_OPTIONS,
        "customers_force_unique_phone": YES_NO_OPTIONS,
        "customers_credit_enabled": YES_NO_OPTIONS,
        "pos_layout": [
            ("grocery_shop", "Retail Layout"),
            ("clothing_shop", "Clothing Shop"),
        ],
        "pos_complete_sale_audio": [
            ("", "Disabled"),
            ("/audio/bubble.mp3", "Bubble"),
            ("/audio/ding.mp3", "Ding"),
            ("/audio/pop.mp3", "Pop"),
            ("/audio/cash-sound.mp3", "Cash Sound"),
        ],
        "pos_new_item_audio": [
            ("", "Disabled"),
            ("/audio/bubble.mp3", "Bubble"),
            ("/audio/ding.mp3", "Ding"),
            ("/audio/pop.mp3", "Pop"),
            ("/audio/cash-sound.mp3", "Cash Sound"),
        ],
        "pos_printing_document": [
            ("invoice", "Invoice"),
            ("receipt", "Receipt"),
        ],
        "pos_printing_enabled_for": [
            ("disabled", "Disabled"),
            ("all_orders", "All Orders"),
            ("partially_paid_orders", "From Partially Paid Orders"),
            ("only_paid_orders", "Only Paid Orders"),
        ],
        "pos_printing_gateway": [("default", "Default Printing (web)")],
        "pos_registers_enabled": YES_NO_OPTIONS,
        "pos_idle_counter": [
            ("disabled", "Disabled"),
            ("5min", "5 Minutes"),
            ("10min", "10 Minutes"),
            ("15min", "15 Minutes"),
            ("20min", "20 Minutes"),
            ("30min", "30 Minutes"),
        ],
        "pos_disbursement": YES_NO_OPTIONS,
        "pos_vat": [
            ("disabled", "Disabled"),
            ("flat_vat", "Flat Rate"),
            ("variable_vat", "Flexible Rate"),
            ("products_vat", "Products Vat"),
        ],
        "pos_tax_type": [
            ("inclusive", "Inclusive"),
            ("exclusive", "Exclusive"),
        ],
        "pos_show_quantity": YES_NO_OPTIONS,
        "pos_items_merge": YES_NO_OPTIONS,
        "pos_allow_wholesale_price": YES_NO_OPTIONS,
        "pos_allow_decimal_quantities": YES_NO_OPTIONS,
        "pos_quick_product": YES_NO_OPTIONS,
        "pos_unit_price_ediable": YES_NO_OPTIONS,
        "pos_prefered_price": [
            ("gross_prices", "Gross Prices"),
            ("net_prices", "Net Prices"),
        ],
        "pos_order_types": [(option["value"], option["label"]) for option in ORDER_TYPE_OPTIONS],
        "pos_numpad": [
            ("default", "Default"),
            ("advanced", "Advanced"),
        ],
        "pos_force_autofocus": YES_NO_OPTIONS,
        "pos_hide_exhausted_products": YES_NO_OPTIONS,
        "pos_hide_empty_categories": YES_NO_OPTIONS,
        "pos_action_permission_enabled": YES_NO_OPTIONS,
        "scale_barcode_enabled": YES_NO_OPTIONS,
        "pos_enable_reordering": YES_NO_OPTIONS,
        "pos_enable_pinned_products": YES_NO_OPTIONS,
        "pos_show_preview_pinned_products": YES_NO_OPTIONS,
        "pos_action_permission_duration": [
            ("1", "1 Minute"),
            ("5", "5 Minutes"),
            ("10", "10 Minutes"),
        ],
        "pos_action_permission_cooldown_features": [
            ("0", "No Cooldown"),
            ("5", "5 Minutes"),
            ("10", "10 Minutes"),
            ("15", "15 Minutes"),
            ("30", "30 Minutes"),
            ("60", "1 Hour"),
        ],
        "scale_barcode_type": [
            ("weight", "Weight"),
            ("price", "Price"),
        ],
        "invoice_receipt_template": [("default", "Default")],
        "invoice_merge_similar_products": YES_NO_OPTIONS,
        "invoice_display_tax_breakdown": YES_NO_OPTIONS,
        "reports_email": YES_NO_OPTIONS,
        "mode": [
            ("wipe_all", "Wipe All"),
            ("wipe_plus_grocery", "Wipe Plus Grocery"),
        ],
    }

    @staticmethod
    def defaultValues():
        return defaultBusinessSettings()

    @staticmethod
    def ensureSettings(user):
        return ensureDefaultOptions(
            company=user.company,
            branch=user.branch,
            user=user,
        )

    @staticmethod
    def ensureOptionValue(company, branch, key, value, user=None):
        return ensureOptionValue(company, branch, key, value, user=user)

    @staticmethod
    def getOptionValue(company, branch, key, default=None):
        from apps.settings.models import Option
        option = Option.objects.filter(company=company, branch=branch, key=key, status=0).first()
        if option is None:
            return default
        return decodeOptionValue(option)

    @staticmethod
    def sourceOptionKey(field):
        return OptionSettingService.OPTION_KEY_MAP.get(
            OptionSettingService.SOURCE_OPTION_ALIASES.get(field, field),
            OptionSettingService.SOURCE_OPTION_ALIASES.get(field, field),
        )

    @staticmethod
    def cleanOptionValue(value):
        if isinstance(value, str):
            return re.sub(r"<[^>]*>", "", value)
        if isinstance(value, list):
            return [OptionSettingService.cleanOptionValue(item) for item in value]
        if isinstance(value, dict):
            return {key: OptionSettingService.cleanOptionValue(item) for key, item in value.items()}
        return value

    @staticmethod
    def formFields(identifier):
        form = OptionSettingService.SETTING_FORMS.get(identifier)
        if form is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to initialize the settings page.")
        fields = []
        for tab in form["tabs"].values():
            fields.extend(tab)
        return fields

    @staticmethod
    def fieldConfig(field):
        name, field_type, label, validation = field[:4]
        description = field[4] if len(field) > 4 else ""
        return name, field_type, label, validation, description

    @staticmethod
    def fieldValue(user, field):
        key = OptionSettingService.sourceOptionKey(field)
        return OptionSettingService.getOptionValue(user.company, user.branch, key)

    @staticmethod
    def optionRows(rows, label):
        options = []
        for row in rows:
            label_value = label(row)
            if not label_value:
                label_value = f"#{row.id}"
            options.append({"value": str(row.id), "label": label_value, "id": row.id, "name": label_value})
        return options

    @staticmethod
    def keyValueOptions(values):
        return [
            {"value": str(value), "label": str(value), "id": str(value), "name": str(value)}
            for value in values
        ]

    @staticmethod
    def labeledOptions(values):
        return [
            {"value": str(value), "label": str(label), "id": str(value), "name": str(label)}
            for value, label in values
        ]

    @staticmethod
    def fieldOptions(user, field):
        base_filters = {
            "company_id": user.company_id,
            "branch_id": user.branch_id,
            "status": 0,
        }
        if field == "registration_role":
            rows = Role.objects.filter(**base_filters).order_by("name")
            return OptionSettingService.optionRows(rows, lambda row: row.name)
        if field == "customers_default":
            rows = Customer.objects.filter(**base_filters).order_by("first_name", "last_name")
            return OptionSettingService.optionRows(
                rows,
                lambda row: (
                    f"{row.first_name or ''} {row.last_name or ''}".strip()
                    or row.phone
                    or row.username
                ),
            )
        if field == "customers_default_group":
            rows = CustomerGroup.objects.filter(**base_filters).order_by("name")
            return OptionSettingService.optionRows(rows, lambda row: row.name)
        if field == "pos_tax_group":
            rows = TaxGroup.objects.filter(**base_filters).order_by("name")
            return OptionSettingService.optionRows(rows, lambda row: row.name)
        if field == "pos_quick_product_default_unit":
            rows = Unit.objects.filter(**base_filters).order_by("name")
            return OptionSettingService.optionRows(rows, lambda row: row.name)
        if field == "pos_registers_default_change_payment_type":
            rows = PaymentType.objects.filter(**base_filters).order_by("priority", "label")
            return OptionSettingService.optionRows(rows, lambda row: row.label)
        if field == "date_format":
            return OptionSettingService.keyValueOptions(OptionSettingService.DATE_FORMAT_OPTIONS)
        if field == "datetime_format":
            return OptionSettingService.keyValueOptions(OptionSettingService.DATETIME_FORMAT_OPTIONS)
        if field == "datetime_timezone":
            return OptionSettingService.keyValueOptions(sorted(zoneinfo.available_timezones()))
        if field in OptionSettingService.ACCOUNT_OPTION_CATEGORIES:
            rows = TransactionAccount.objects.filter(
                **base_filters,
                category_identifier=OptionSettingService.ACCOUNT_OPTION_CATEGORIES[field],
                sub_category_id__isnull=False,
            ).order_by("name")
            return OptionSettingService.optionRows(rows, lambda row: row.name)
        if field in OptionSettingService.STATIC_FIELD_OPTIONS:
            return OptionSettingService.labeledOptions(OptionSettingService.STATIC_FIELD_OPTIONS[field])
        return None

    @staticmethod
    def isTruthySourceOption(value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).lower() in {"yes", "true", "1", "enabled"}

    @staticmethod
    def formTabs(identifier, user):
        form = OptionSettingService.SETTING_FORMS.get(identifier)
        if form is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to initialize the settings page.")
        tabs = {tab_identifier: list(fields) for tab_identifier, fields in form["tabs"].items()}
        if identifier != "pos":
            return tabs

        registers_enabled = OptionSettingService.isTruthySourceOption(
            OptionSettingService.getOptionValue(user.company, user.branch, "registers_enabled")
        )
        if not registers_enabled:
            tabs["registers"] = [
                field for field in tabs.get("registers", []) if field[0] == "pos_registers_enabled"
            ]

        if OptionSettingService.getOptionValue(user.company, user.branch, "pos_vat") != "flat_vat":
            tabs["vat"] = [
                field for field in tabs.get("vat", []) if field[0] == "pos_vat"
            ]

        action_permission_enabled = OptionSettingService.isTruthySourceOption(
            OptionSettingService.getOptionValue(user.company, user.branch, "pos_action_permission_enabled")
        )
        if not action_permission_enabled:
            tabs.pop("pos_actions", None)

        scale_barcode_enabled = OptionSettingService.isTruthySourceOption(
            OptionSettingService.getOptionValue(user.company, user.branch, "scale_barcode_enabled")
        )
        if not scale_barcode_enabled:
            tabs.pop("scale-barcode", None)
        return tabs

    @staticmethod
    def getForm(identifier, user):
        OptionSettingService.ensureSettings(user)
        form = OptionSettingService.SETTING_FORMS.get(identifier)
        if form is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to initialize the settings page.")
        tabs = {}
        for tab_identifier, fields in OptionSettingService.formTabs(identifier, user).items():
            tabs[tab_identifier] = {
                "identifier": tab_identifier,
                "label": tab_identifier.replace("-", " ").replace("_", " ").title(),
                "fields": [
                    {
                        "name": name,
                        "type": field_type,
                        "label": label,
                        "validation": validation,
                        "description": description,
                        "value": OptionSettingService.fieldValue(user, name),
                        "options": OptionSettingService.fieldOptions(user, name),
                    }
                    for name, field_type, label, validation, description in [
                        OptionSettingService.fieldConfig(field) for field in fields
                    ]
                ],
            }
        return successResponse(
            "Settings form retrieved successfully.",
            data={
                "identifier": identifier,
                "title": form["title"],
                "description": form["description"],
                "tabs": tabs,
            },
        )

    @staticmethod
    def saveForm(identifier, user, data):
        from apps.settings.models import Option

        allowed_fields = {field[0] for fields in OptionSettingService.formTabs(identifier, user).values() for field in fields}
        saved = {}
        for field, value in (data or {}).items():
            if field not in allowed_fields:
                continue
            key = OptionSettingService.sourceOptionKey(field)
            if value is None:
                Option.objects.filter(company=user.company, branch=user.branch, key=key, status=0).delete()
                continue
            value = OptionSettingService.cleanOptionValue(value)
            if key == "order_types":
                value = OptionSettingService.normalizeOrderTypes(value)
            if key == "currency_precision":
                precision = int(value or 0)
                if precision < 0 or precision > 6:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Currency precision must be between 0 and 6.")
                value = precision
            ensureOptionValue(user.company, user.branch, key, value, user=user)
            saved[field] = value
        return successResponse("The form has been successfully saved.", data=saved)

    @staticmethod
    def optionValue(options):
        return buildBusinessSettingsFromOptions(options)

    @staticmethod
    def normalizeOrderTypes(order_types):
        allowed_values = [option["value"] for option in ORDER_TYPE_OPTIONS]
        selected = []
        for order_type in order_types or []:
            if order_type not in allowed_values:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid order type.")
            if order_type not in selected:
                selected.append(order_type)
        if not selected:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Select at least one order type.")
        return selected

    @staticmethod
    def get(user):
        data = OptionSettingService.buildSessionSettings(user)
        return successResponse(
            "Business settings retrieved successfully.",
            data=data,
        )

    @staticmethod
    def buildSessionSettings(user):
        settings_rows = OptionSettingService.ensureSettings(user)
        setting_data = {
            field: OptionSettingService.optionValue(settings_rows).get(field)
            for field in BUSINESS_SETTING_FIELDS
        }
        if not setting_data["order_types"]:
            setting_data["order_types"] = ["takeaway", "delivery"]
        setting_data["order_types"] = [
            "takeaway" if order_type == "take_order" else order_type
            for order_type in setting_data["order_types"]
        ]
        order_types = [
            {"value": option["value"], "label": option["label"], "enabled": option["value"] in setting_data["order_types"]}
            for option in ORDER_TYPE_OPTIONS
        ]
        return {
            "settings": setting_data,
            "order_types": order_types,
        }

    @staticmethod
    def update(user, data):
        OptionSettingService.ensureSettings(user)
        setting_data = OptionSettingService.defaultValues()
        for field in BUSINESS_SETTING_FIELDS:
            if field == "order_types":
                continue
            if field not in OPTION_KEY_MAP:
                setting_data[field] = bool(data.get(field))
                continue
            if field in OptionSettingService.INTEGER_SETTING_FIELDS:
                val = int(data.get(field) or OptionSettingService.defaultValues().get(field) or 0)
                if field == "currency_precision" and (val < 0 or val > 6):
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Currency precision must be between 0 and 6.")
                setting_data[field] = val
            elif field in OptionSettingService.STRING_SETTING_FIELDS:
                setting_data[field] = str(data.get(field) or OptionSettingService.defaultValues().get(field) or "")
            else:
                setting_data[field] = bool(data.get(field))
        setting_data["order_types"] = OptionSettingService.normalizeOrderTypes(data.get("order_types"))
        for field, key in OPTION_KEY_MAP.items():
            ensureOptionValue(
                user.company,
                user.branch,
                key,
                setting_data.get(field),
                user=user,
            )
        return OptionSettingService.get(user)


class PaymentTypeService:
    @staticmethod
    def normalizeIdentifier(identifier: str, label: str):
        return slugify(identifier or label)

    @staticmethod
    def activeToStatus(data):
        if "active" not in data:
            return 0
        return 0 if bool(data.get("active")) else 1

    @staticmethod
    def paymentTypeData(row):
        row["active"] = row.get("status") == 0
        row["active_label"] = "Yes" if row["active"] else "No"
        row["readonly_label"] = "Yes" if row.get("readonly") else "No"
        return row

    @staticmethod
    def ensureDefaultPaymentTypes(company, branch):
        seeded = []
        for item in DEFAULT_PAYMENT_TYPES:
            payment_type, created = commonQuery.getOrCreateRecord(
                PaymentType,
                {
                    "company_id": company.id,
                    "branch_id": branch.id,
                    "identifier": item["identifier"],
                },
                defaults={
                    "label": item["label"],
                    "description": item["description"],
                    "readonly": True,
                    "priority": item["priority"],
                    "status": 0,
                },
                tenant_config={},
                return_plain=False,
            )
            update_fields = []
            if not payment_type.readonly:
                payment_type.readonly = True
                update_fields.append("readonly")
            if payment_type.priority != item["priority"] and created:
                payment_type.priority = item["priority"]
                update_fields.append("priority")
            if update_fields:
                payment_type.save(update_fields=update_fields)
            seeded.append(serializeModelInstance(payment_type))

        return seeded

    @staticmethod
    def resolvePaymentType(identifier, request, required=True):
        normalized = PaymentTypeService.normalizeIdentifier(identifier or "", identifier or "")
        if not normalized:
            if required:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment type is required.")
            return ""

        payment_type = commonQuery.branchScopedQueryset(
            PaymentType,
            {"identifier": normalized, "status": 0},
            request,
        ).first()
        if payment_type is None:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid payment type.")
        return payment_type.identifier

    @staticmethod
    def dropdownList(request):
        items = (
            commonQuery.branchScopedQueryset(PaymentType, {"status": 0}, request)
            .order_by("priority", "label")
            .values("identifier", "label")
        )
        return successResponse(
            "Payment types retrieved successfully.",
            data=[{"value": item["identifier"], "label": item["label"]} for item in items],
        )

    @staticmethod
    def listPaymentTypes(data, request):
        field_config = [["label", True, True], ["identifier", True, True], ["description", True, False]]
        res = commonQuery.fetchPaginatedData(
            PaymentType,
            data,
            field_config,
            {
                "attributes": ["id", "label", "identifier", "description", "readonly", "priority", "status", "created_at", "user__username"],
                "order": ["priority", "label"],
            },
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        for item in res["items"]:
            item["user_username"] = item.pop("user__username", None)
            PaymentTypeService.paymentTypeData(item)
        return res

    @staticmethod
    def createPaymentType(data, request):
        payload = dict(data or {})
        payload.pop("active", None)
        identifier = PaymentTypeService.normalizeIdentifier(data.get("identifier") or "", data.get("label") or "")
        if not identifier:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment identifier is required.")
        if identifier in paymentTypeValues():
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Default payment identifiers are reserved.")
        validateUniqueFields(
            PaymentType,
            {"label": data.get("label"), "identifier": identifier},
            request=request,
            scope="branch",
            case_insensitive=["label"],
            status_in=None,
            messages={
                "label": "Payment label already exists.",
                "identifier": "Payment identifier already exists.",
            },
        )
        payment_type = commonQuery.createRecord(
            PaymentType,
            {
                **payload,
                "identifier": identifier,
                "readonly": False,
                "priority": max(int(data.get("priority") or 0), 0),
                "status": PaymentTypeService.activeToStatus(data),
            },
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        return successResponse("Payment type created successfully.", data=PaymentTypeService.paymentTypeData(payment_type))

    @staticmethod
    def getPaymentType(payment_type_id, request):
        payment_type = commonQuery.findOneRecord(
            PaymentType,
            payment_type_id,
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        if payment_type is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")
        return PaymentTypeService.paymentTypeData(payment_type)

    @staticmethod
    def updatePaymentType(payment_type_id, data, request):
        payload = dict(data or {})
        payload.pop("active", None)
        with transaction.atomic():
            payment_type = commonQuery.branchScopedQueryset(
                PaymentType,
                {"id": payment_type_id, "status__in": [0, 1]},
                request,
            ).first()
            if payment_type is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")

            if payment_type.readonly:
                identifier = payment_type.identifier
                validateUniqueFields(
                    PaymentType,
                    {"label": data.get("label"), "identifier": identifier},
                    request,
                    scope="branch",
                    exclude_id=payment_type_id,
                    case_insensitive=["label"],
                    status_in=None,
                    messages={
                        "label": "Payment label already exists.",
                        "identifier": "Payment identifier already exists.",
                    },
                )
            else:
                identifier = PaymentTypeService.normalizeIdentifier(data.get("identifier") or "", data.get("label") or "")
                if not identifier:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment identifier is required.")
                if identifier in paymentTypeValues():
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Default payment identifiers are reserved.")
                validateUniqueFields(
                    PaymentType,
                    {"label": data.get("label"), "identifier": identifier},
                    request,
                    scope="branch",
                    exclude_id=payment_type_id,
                    case_insensitive=["label"],
                    status_in=None,
                    messages={
                        "label": "Payment label already exists.",
                        "identifier": "Payment identifier already exists.",
                    },
                )

            updated = commonQuery.updateRecordById(
                PaymentType,
                payment_type_id,
                {
                    **payload,
                    "identifier": identifier,
                    "readonly": payment_type.readonly,
                    "priority": max(int(data.get("priority") or 0), 0),
                    "status": PaymentTypeService.activeToStatus(data),
                },
                request=request,
                tenant_config={"company_id": True, "branch_id": True},
            )
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")
            return PaymentTypeService.paymentTypeData(updated)

    @staticmethod
    def deletePaymentTypes(data, request):
        ids = data.get("ids") or []
        ids = ids if isinstance(ids, list) else [ids]
        success_count = 0
        error_count = 0
        for payment_type_id in ids:
            payment_type = commonQuery.branchScopedQueryset(
                PaymentType,
                {"id": payment_type_id, "status__in": [0, 1]},
                request,
            ).first()
            if payment_type is None:
                error_count += 1
                continue
            if payment_type.readonly:
                error_count += 1
                break
            success_count += commonQuery.softDeleteById(
                PaymentType,
                payment_type_id,
                request=request,
                tenant_config={"company_id": True, "branch_id": True},
            )
        if success_count == 0 and error_count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")
        return {"deleted_count": success_count, "success": success_count, "error": error_count}

    @staticmethod
    def updatePaymentTypeStatus(data, request):
        status = data.get("status")
        ids = data.get("ids") or []
        ids = ids if isinstance(ids, list) else [ids]
        if commonQuery.branchScopedQueryset(PaymentType, {"id__in": ids, "readonly": True}, request).exists():
            raise api_error(
                400,
                ErrorCodes.BAD_REQUEST,
                "Default payment types cannot be deactivated.",
            )
        count = commonQuery.updateStatusById(
            PaymentType,
            ids,
            status,
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")
        return {"updated_count": count, "status": status}


class MediaService:
    SOURCE_MIME_TYPES = {
        "aac": "audio/aac",
        "abw": "application/x-abiword",
        "arc": "application/octet-stream",
        "avi": "video/x-msvideo",
        "azw": "application/vnd.amazon.ebook",
        "bin": "application/octet-stream",
        "bmp": "image/bmp",
        "bz": "application/x-bzip",
        "bz2": "application/x-bzip2",
        "csh": "application/x-csh",
        "css": "text/css",
        "csv": "text/csv",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "eot": "application/vnd.ms-fontobject",
        "epub": "application/epub+zip",
        "gif": "image/gif",
        "htm": "text/html",
        "html": "text/html",
        "ico": "image/x-icon",
        "ics": "text/calendar",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "js": "application/javascript",
        "json": "application/json",
        "mpeg": "video/mpeg",
        "odp": "application/vnd.oasis.opendocument.presentation",
        "ods": "application/vnd.oasis.opendocument.spreadsheet",
        "odt": "application/vnd.oasis.opendocument.text",
        "oga": "audio/ogg",
        "ogv": "video/ogg",
        "ogx": "application/ogg",
        "otf": "font/otf",
        "png": "image/png",
        "pdf": "application/pdf",
        "ppt": "application/vnd.ms-powerpoint",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "rar": "application/x-rar-compressed",
        "rtf": "application/rtf",
        "sh": "application/x-sh",
        "svg": "image/svg+xml",
        "tar": "application/x-tar",
        "ts": "application/typescript",
        "ttf": "font/ttf",
        "wav": "audio/x-wav",
        "weba": "audio/webm",
        "webm": "video/webm",
        "webp": "image/webp",
        "woff": "font/woff",
        "woff2": "font/woff2",
        "xhtml": "application/xhtml+xml",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xml": "application/xml",
        "xul": "application/vnd.mozilla.xul+xml",
        "zip": "application/zip",
        "7z": "application/x-7z-compressed",
    }
    IMAGE_EXTENSIONS = {"bmp", "gif", "ico", "jpeg", "jpg", "png", "svg", "webp"}
    MAX_FILE_SIZE = 5 * 1024 * 1024

    @staticmethod
    def mediaData(media):
        original_path = f"{media.slug}.{media.extension}"
        original_url = f"{settings.UPLOAD_URL}{original_path}"
        data = {
            "id": media.id,
            "created_at": media.created_at,
            "updated_at": media.updated_at,
            "name": media.name,
            "extension": media.extension,
            "slug": media.slug,
            "sizes": {"original": original_url},
        }
        if media.extension in MediaService.IMAGE_EXTENSIONS:
            data["sizes"]["thumb"] = original_url
        user = getattr(media, "user", None)
        data["user"] = (
            {
                "id": user.id,
                "username": user.username,
                "full_name": getattr(user, "full_name", "") or user.get_full_name() or user.username,
            }
            if user
            else None
        )
        return jsonsafe(data)

    @staticmethod
    def buildStoredName(file, request=None):
        path = Path(getattr(file, "name", "upload"))
        extension = path.suffix.lstrip(".").lower()
        base_name = slugify(path.stem) or "upload"
        year = timezone.now().strftime("%Y")
        month = timezone.now().strftime("%m")
        candidate = base_name
        suffix = 1
        while commonQuery.branchScopedQueryset(
            Media,
            {"name": candidate, "extension": extension, "status__in": [0, 1]},
            request,
        ).exists():
            candidate = f"{base_name}-{suffix}"
            suffix += 1
        return candidate, extension, f"{year}/{month}/{candidate}"

    @staticmethod
    def upload(file, request, folder="", entity_type="", entity_id=None, alt_text=""):
        if not file:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "File is required.")
        if getattr(file, "size", 0) > MediaService.MAX_FILE_SIZE:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "File size must be 5MB or less.")
        content_type = getattr(file, "content_type", "") or ""
        extension = Path(getattr(file, "name", "upload")).suffix.lstrip(".").lower()
        if extension not in MediaService.SOURCE_MIME_TYPES:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unsupported media file type.")
        if content_type and content_type != MediaService.SOURCE_MIME_TYPES.get(extension):
            allowed_image_match = extension in ["jpg", "jpeg"] and content_type == "image/jpeg"
            if not allowed_image_match:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Unsupported media file type.")

        name, extension, slug = MediaService.buildStoredName(file, request)
        storage = FileSystemStorage(location=settings.UPLOAD_ROOT, base_url=settings.UPLOAD_URL)
        storage.save(f"{slug}.{extension}", file)
        media = commonQuery.createRecord(
            Media,
            {
                "name": name,
                "extension": extension,
                "slug": slug,
            },
            request=request,
            tenant_config=True,
        )
        media_instance = commonQuery.findOneInstance(
            Media,
            media["id"],
            request=request,
            tenant_config=True,
        )
        return successResponse("Media uploaded successfully.", data=MediaService.mediaData(media_instance))

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            Media,
            data,
            [["name", True, True], ["extension", True, True], ["slug", True, True]],
            {
                "attributes": [
                    "id",
                    "name",
                    "extension",
                    "slug",
                    "user_id",
                    "created_at",
                    "updated_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        media_ids = [item["id"] for item in result["items"]]
        instances = commonQuery.branchScopedQueryset(
            Media,
            {"id__in": media_ids},
            request,
        ).select_related("user")
        media_map = {media.id: MediaService.mediaData(media) for media in instances}
        result["items"] = [media_map.get(item["id"], item) for item in result["items"]]
        return successResponse("Media retrieved successfully.", data=result)

    @staticmethod
    def update(media_id, data, request):
        data = {key: value for key, value in data.items() if key in ["name"]}
        updated = commonQuery.updateRecordById(Media, media_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Media not found.")
        media = commonQuery.findOneInstance(Media, media_id, request=request, tenant_config=True)
        return successResponse("The media name was successfully updated.", data=MediaService.mediaData(media))

    @staticmethod
    def delete(data, request):
        ids = data.get("ids")
        ids = ids if isinstance(ids, list) else [ids]
        media_items = commonQuery.branchScopedQueryset(Media, {"id__in": ids, "status__in": [0, 1]}, request)
        storage = FileSystemStorage(location=settings.UPLOAD_ROOT, base_url=settings.UPLOAD_URL)
        for media in media_items:
            storage.delete(f"{media.slug}.{media.extension}")

        count = commonQuery.softDeleteById(Media, ids, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Media not found.")
        return successResponse("The media has been deleted.")


class NotificationService:
    @staticmethod
    def generateIdentifier():
        return f"notification-{timezone.now().strftime('%d-%m-%y')}-{timezone.now().timestamp()}"

    @staticmethod
    def upsertForUser(*, user_id, title, description, url="#", identifier=None, source="system", dismissable=True, actions=None, request=None):
        identifier = identifier or NotificationService.generateIdentifier()
        notification = commonQuery.branchScopedQueryset(
            Notification,
            {
                "user_id": user_id,
                "identifier": identifier,
                "status__in": [0, 1],
            },
            request,
        ).first()
        payload = {
            "user_id": user_id,
            "identifier": identifier,
            "title": title,
            "description": description,
            "url": url or "#",
            "source": source or "system",
            "dismissable": dismissable,
            "actions": actions or None,
        }
        if notification is None:
            return commonQuery.createRecord(Notification, payload, request=request, tenant_config=True)
        return commonQuery.updateRecordById(Notification, notification.id, payload, request=request, tenant_config=True)

    @staticmethod
    def create(data, request):
        data["description"] = data.get("description") or data.pop("message", "")
        data["source"] = data.get("source") or data.pop("source_type", "system")
        data["url"] = data.get("url") or data.pop("action_url", "#")
        data["actions"] = data.get("actions") or data.pop("payload", None)
        data["identifier"] = data.get("identifier") or NotificationService.generateIdentifier()
        notification = NotificationService.upsertForUser(
            user_id=data.get("user_id") or request.user.id,
            title=data.get("title"),
            description=data.get("description"),
            url=data.get("url"),
            identifier=data.get("identifier"),
            source=data.get("source"),
            dismissable=data.get("dismissable", True),
            actions=data.get("actions"),
            request=request,
        )
        return successResponse("Notification created successfully.", data=notification)

    @staticmethod
    def push(*, title, message="", notification_type="info", source_type="system", source_id=None, user_id=None, action_url="", payload=None, request=None):
        return NotificationService.upsertForUser(
            user_id=user_id or (request.user.id if request else None),
            identifier=f"{source_type}-{source_id or 'general'}",
            title=title,
            description=message,
            source=source_type,
            url=action_url or "#",
            actions=payload,
            request=request,
        )

    @staticmethod
    def dispatchForUsers(users, *, title, description="", url="#", identifier=None, source="system", dismissable=True, actions=None, request=None):
        return [
            NotificationService.upsertForUser(
                user_id=user.id,
                title=title,
                description=description,
                url=url,
                identifier=identifier,
                source=source,
                dismissable=dismissable,
                actions=actions,
                request=request,
            )
            for user in users
        ]

    @staticmethod
    def dispatchForRoleNamespaces(namespaces, *, title, description="", url="#", identifier=None, source="system", dismissable=True, actions=None, request=None):
        roles = commonQuery.branchScopedQueryset(Role, {"namespace__in": namespaces, "status": 0}, request)
        users = commonQuery.branchScopedQueryset(User, {"role__in": roles, "status": 0}, request)
        return NotificationService.dispatchForUsers(
            users,
            title=title,
            description=description,
            url=url,
            identifier=identifier,
            source=source,
            dismissable=dismissable,
            actions=actions,
            request=request,
        )

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            Notification,
            data,
            [["title", True, True], ["description", True, True], ["identifier", True, True], ["source", True, True]],
            {
                "attributes": [
                    "id",
                    "user_id",
                    "user__full_name",
                    "identifier",
                    "title",
                    "description",
                    "source",
                    "url",
                    "dismissable",
                    "actions",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Notifications retrieved successfully.", data=result)

    @staticmethod
    def unreadCount(request):
        count = commonQuery.branchScopedQueryset(
            Notification,
            {"status__in": [0, 1]},
            request,
        ).filter(user_id__in=[request.user.id, None]).count()
        return successResponse("Unread notification count retrieved successfully.", data={"count": count})

    @staticmethod
    def markRead(data, request):
        ids = data.get("ids")
        if not isinstance(ids, list):
            ids = [ids]
        count = commonQuery.branchScopedQueryset(
            Notification,
            {"id__in": ids, "status__in": [0, 1]},
            request,
        ).update(status=1)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Notification not found.")
        return successResponse("Notifications marked as read successfully.", data={"updated_count": count})

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Notification, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Notification not found.")
        return successResponse("Notifications deleted successfully.")


class JobQueueService:
    DEFAULT_QUEUE = "default"

    @staticmethod
    def handlers():
        from apps.accounting.services import TransactionService
        from apps.catalog.services import CategoryService, ProductStockService
        from apps.customers.services import CustomerAccountService
        from apps.purchases.services import PurchaseOrderService
        from apps.registers.services import RegisterService
        from apps.reports.services import ReportService
        from apps.rewards.services import CustomerRewardService
        from apps.sales.services import SaleService

        handlers = {}
        handlers.update(TransactionService.jobHandlers())
        handlers.update(CategoryService.jobHandlers())
        handlers.update(ProductStockService.jobHandlers())
        handlers.update(CustomerAccountService.jobHandlers())
        handlers.update(PurchaseOrderService.jobHandlers())
        handlers.update(RegisterService.jobHandlers())
        handlers.update(ReportService.jobHandlers())
        handlers.update(CustomerRewardService.jobHandlers())
        handlers.update(SaleService.jobHandlers())
        source_job_aliases = {
            "AccountingReflectionJob": "accounting_reflection",
            "ApplyCustomerRewardJob": "apply_customer_reward",
            "CheckCustomerAccountJob": "check_customer_account",
            "ClearHoldOrdersJob": "clear_hold_orders",
            "ComputeCategoryProductsJob": "compute_category_products",
            "ComputeDashboardMonthReportJob": "compute_dashboard_month",
            "ComputeDayReportJob": "compute_day_report",
            "ComputeYearlyReportJob": "compute_yearly_report",
            "CreateExpenseFromRefundJob": "record_refund_shipping_transaction",
            "DecreaseCustomerPurchasesJob": "decrease_customer_purchases_from_refund",
            "DeleteAccountingReflectionJob": "delete_accounting_reflection",
            "DetectLowStockProductsJob": "detect_low_stock_products",
            "DetectScheduledTransactionsJob": "detect_scheduled_transactions",
            "EnsureCombinedProductHistoryExistsJob": "ensure_combined_product_history",
            "ExecuteDelayedTransactionJob": "execute_delayed_transaction",
            "HandleStockAdjustmentJob": "handle_stock_adjustment",
            "IncreaseCashierStatsJob": "increase_cashier_stats",
            "InitializeDailyReportJob": "initialize_daily_report",
            "ProcessCustomerOwedAndRewardsJob": "process_customer_owed_and_rewards",
            "ProcessTransactionJob": "prepare_transaction_history",
            "ProcurementRefreshJob": "refresh_procurement",
            "PurgeOrderStorageJob": "purge_order_storage",
            "RecordOrderChangeJob": "record_order_change",
            "RecordTransactionForShippingJob": "record_refund_shipping_transaction",
            "ReduceCashierStatsFromRefundJob": "reduce_cashier_stats_from_refund",
            "RefreshOrderJob": "refresh_order",
            "RefreshReportJob": "refresh_report",
            "ResolveInstalmentJob": "resolve_instalments",
            "SaveOrderSettingJob": "save_order_settings",
            "StockProcurementJob": "stock_awaiting_procurements",
            "StoreCustomerPaymentHistoryJob": "store_customer_payment_history",
            "TrackCashRegisterJob": "track_cash_register_payment",
            "TrackLaidAwayOrdersJob": "track_laid_away_orders",
            "TrackOrderCouponsJob": "track_order_coupons",
            "TriggerRecurringTransactionJob": "trigger_recurring_transactions",
            "UncountDeletedOrderForCashierJob": "uncount_deleted_order_for_cashier",
            "UncountDeletedOrderForCustomerJob": "uncount_deleted_order_for_customer",
            "UpdateCashRegisterBalanceFromHistoryJob": "refresh_cash_register",
        }
        for source_job, handler_name in source_job_aliases.items():
            if handler_name in handlers:
                handlers[source_job] = handlers[handler_name]
        return handlers

    @staticmethod
    def timestamp(value=None):
        if value is None:
            return int(time.time())
        if hasattr(value, "timestamp"):
            return int(value.timestamp())
        return int(value)

    @staticmethod
    def encodePayload(job_name, data=None):
        return json.dumps(
            {
                "job": job_name,
                "data": data or {},
            },
            default=str,
        )

    @staticmethod
    def decodePayload(payload):
        if isinstance(payload, dict):
            return payload
        try:
            decoded = json.loads(payload or "{}")
        except json.JSONDecodeError:
            decoded = {}
        return decoded if isinstance(decoded, dict) else {}

    @staticmethod
    def payloadMatches(payload, job_name):
        return JobQueueService.decodePayload(payload).get("job") == job_name

    @staticmethod
    def hasJobSince(job_name, branch, since):
        since_ts = JobQueueService.timestamp(since)
        if any(
            JobQueueService.payloadMatches(job.payload, job_name)
            for job in Job.objects.filter(branch=branch, created_at__gte=since_ts)
        ):
            return True
        return any(
            JobQueueService.payloadMatches(failed.payload, job_name)
            for failed in FailedJob.objects.filter(branch=branch, failed_at__gte=since)
        )

    @staticmethod
    def enqueue(job_name, data=None, *, request=None, queue=None, available_at=None):
        if request is None:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Request context is required to enqueue a tenant job.")
        return commonQuery.createInstance(
            Job,
            {
                "queue": queue or JobQueueService.DEFAULT_QUEUE,
                "payload": JobQueueService.encodePayload(job_name, data),
                "attempts": 0,
                "reserved_at": None,
                "available_at": JobQueueService.timestamp(available_at),
                "created_at": JobQueueService.timestamp(),
            },
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def reserveNext(*, queue=None, now=None):
        current_time = JobQueueService.timestamp(now)
        with transaction.atomic():
            queryset = commonQuery.scopedQueryset(Job, {}, tenant_config={}).select_for_update(
                skip_locked=connection.features.has_select_for_update_skip_locked
            )
            job = (
                queryset
                .filter(
                    queue=queue or JobQueueService.DEFAULT_QUEUE,
                    reserved_at__isnull=True,
                    available_at__lte=current_time,
                    status=0,
                )
                .order_by("id")
                .first()
            )
            if job is None:
                return None
            job.reserved_at = current_time
            job.attempts = int(job.attempts or 0) + 1
            job.save(update_fields=["reserved_at", "attempts"])
            return job

    @staticmethod
    def complete(job):
        job.delete()

    @staticmethod
    def fail(job, exc):
        commonQuery.createInstance(
            FailedJob,
            {
                "user_id": job.user_id,
                "company_id": job.company_id,
                "branch_id": job.branch_id,
                "queue": job.queue,
                "connection": "database",
                "payload": job.payload,
                "exception": str(exc),
                "status": 0,
            },
            tenant_config={},
        )
        job.delete()

    @staticmethod
    def release(job, delay=60):
        job.reserved_at = None
        job.available_at = JobQueueService.timestamp() + int(delay)
        job.save(update_fields=["reserved_at", "available_at"])

    @staticmethod
    def runNext(handlers, *, queue=None):
        job = JobQueueService.reserveNext(queue=queue)
        if job is None:
            return None
        job_id = job.id
        payload = JobQueueService.decodePayload(job.payload)
        handler = handlers.get(payload.get("job"))
        if handler is None:
            JobQueueService.fail(job, f"Missing job handler: {payload.get('job')}")
            return {"status": "failed", "job_id": job_id, "reason": "missing_handler"}
        try:
            handler(payload.get("data") or {}, job)
        except Exception as exc:
            JobQueueService.fail(job, exc)
            return {"status": "failed", "job_id": job_id, "reason": str(exc)}
        JobQueueService.complete(job)
        return {"status": "completed", "job_id": job_id}

    @staticmethod
    def listPendingJobs(data, request):
        field_config = [
            ["id", False, True],
            ["queue", True, True],
            ["payload", True, False],
            ["attempts", False, True],
            ["available_at", False, True],
            ["created_at", False, True],
            ["reserved_at", False, True],
        ]
        return commonQuery.fetchPaginatedData(
            Job,
            data,
            field_config,
            {
                "attributes": ["id", "queue", "payload", "attempts", "reserved_at", "available_at", "created_at", "status"],
                "order": ["-id"],
            },
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )

    @staticmethod
    def listFailedJobs(data, request):
        field_config = [
            ["id", False, True],
            ["queue", True, True],
            ["connection", True, True],
            ["payload", True, False],
            ["exception", True, False],
            ["failed_at", False, True],
        ]
        return commonQuery.fetchPaginatedData(
            FailedJob,
            data,
            field_config,
            {
                "attributes": ["id", "queue", "connection", "payload", "exception", "failed_at", "status"],
                "order": ["-id"],
            },
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )

    @staticmethod
    def retryFailedJob(failed_job_id, request):
        failed_job = commonQuery.branchScopedQueryset(
            FailedJob,
            {"id": failed_job_id, "status": 0},
            request,
        ).first()
        if failed_job is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Failed job not found.")
        
        with transaction.atomic():
            commonQuery.createInstance(
                Job,
                {
                    "queue": failed_job.queue or JobQueueService.DEFAULT_QUEUE,
                    "payload": failed_job.payload,
                    "attempts": 0,
                    "reserved_at": None,
                    "available_at": JobQueueService.timestamp(),
                    "created_at": JobQueueService.timestamp(),
                    "status": 0,
                },
                request=request,
                tenant_config=True,
            )
            failed_job.delete()
        
        return successResponse("Failed job retried successfully.")

    @staticmethod
    def deleteFailedJob(failed_job_id, request):
        failed_job = commonQuery.branchScopedQueryset(
            FailedJob,
            {"id": failed_job_id, "status": 0},
            request,
        ).first()
        if failed_job is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Failed job not found.")
        failed_job.delete()
        return successResponse("Failed job deleted successfully.")


class SchedulerService:
    SCHEDULES = [
        {"job": "detect_scheduled_transactions", "cadence": "every_five_minutes", "label": "Every 5 minutes"},
        {"job": "ensure_combined_product_history", "cadence": "hourly", "label": "Hourly"},
        {"job": "detect_low_stock_products", "cadence": "daily_at", "hour": 0, "minute": 2, "label": "Daily at 00:02"},
        {"job": "stock_awaiting_procurements", "cadence": "daily_at", "hour": 0, "minute": 5, "label": "Daily at 00:05"},
        {
            "job": "trigger_recurring_transactions",
            "cadence": "daily_at",
            "hour": 0,
            "minute": 10,
            "label": "Daily at 00:10",
            "data": lambda now: {"date": now.date().isoformat()},
        },
        {"job": "track_laid_away_orders", "cadence": "daily_at", "hour": 13, "minute": 0, "label": "Daily at 13:00"},
        {"job": "clear_hold_orders", "cadence": "daily_at", "hour": 14, "minute": 0, "label": "Daily at 14:00"},
        {"job": "purge_order_storage", "cadence": "daily_at", "hour": 15, "minute": 0, "label": "Daily at 15:00"},
    ]

    @staticmethod
    def shouldRun(schedule, now):
        cadence = schedule["cadence"]
        if cadence == "every_five_minutes":
            return now.minute % 5 == 0
        if cadence == "hourly":
            return now.minute == 0
        if cadence == "daily_at":
            return now.hour == schedule["hour"] and now.minute == schedule["minute"]
        return False

    @staticmethod
    def sinceFor(schedule, now):
        if schedule["cadence"] == "every_five_minutes":
            slot_minute = now.minute - (now.minute % 5)
            return now.replace(minute=slot_minute, second=0, microsecond=0)
        if schedule["cadence"] == "hourly":
            return now.replace(minute=0, second=0, microsecond=0)
        return timezone.make_aware(datetime.datetime.combine(now.date(), datetime.time.min))

    @staticmethod
    def branchRequest(branch):
        user = User.objects.filter(branch=branch, status=0).order_by("-is_superuser", "id").first()
        if user is None:
            return None
        return SimpleNamespace(user=user)

    @staticmethod
    def enqueueDue(now=None, force=False):
        now = timezone.localtime(now or timezone.now())
        enqueued = []
        skipped = []

        for branch in Branch.objects.filter(status=0).select_related("company"):
            request = SchedulerService.branchRequest(branch)
            if request is None:
                skipped.append({"branch_id": branch.id, "reason": "missing_active_user"})
                continue

            for schedule in SchedulerService.SCHEDULES:
                if not SchedulerService.shouldRun(schedule, now):
                    continue

                job_name = schedule["job"]
                since = SchedulerService.sinceFor(schedule, now)
                if not force and JobQueueService.hasJobSince(job_name, branch, since):
                    skipped.append({"branch_id": branch.id, "job": job_name, "reason": "already_enqueued"})
                    continue

                data_builder = schedule.get("data")
                data = data_builder(now) if callable(data_builder) else {}
                job = JobQueueService.enqueue(job_name, data, request=request)
                enqueued.append(
                    {
                        "branch_id": branch.id,
                        "job_id": job.id,
                        "job": job_name,
                        "schedule": schedule["label"],
                    }
                )

        return {"checked_at": now.isoformat(), "enqueued": enqueued, "skipped": skipped}
