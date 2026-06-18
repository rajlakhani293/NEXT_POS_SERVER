# type: ignore
import json

from apps.common.responses import successResponse
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.settingsapi.models import Option


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


class OptionSettingService:
    OPTION_KEY_MAP = {
        "allow_decimal_quantities": "ns_pos_allow_decimal_quantities",
        "quick_product_enabled": "ns_pos_quick_product",
        "show_quantity": "ns_pos_show_quantity",
        "currency_precision": "ns_currency_precision",
        "hide_empty_categories": "ns_pos_hide_empty_categories",
        "unit_price_editable": "ns_pos_unit_price_ediable",
        "order_types": "ns_pos_order_types",
        "default_change_payment_type": "ns_pos_registers_default_change_payment_type",
    }

    EXTRA_OPTION_DEFAULTS = {
        "ns_registration_enabled": "no",
        "ns_store_name": "NexoPOS",
        "ns_store_language": "en",
        "ns_scale_barcode_product_length": 4,
    }

    @staticmethod
    def defaultValues():
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

    @staticmethod
    def ensureCompanySettings(company):
        return OptionSettingService.defaultValues()

    @staticmethod
    def ensureSettings(user):
        return OptionSettingService.ensureOptions(
            company=user.company,
            branch=user.branch,
            user=user,
        )

    @staticmethod
    def encodeValue(value):
        if isinstance(value, (list, dict)):
            return json.dumps(value), True
        if value is True:
            return "yes", False
        if value is False:
            return "no", False
        return str(value or ""), False

    @staticmethod
    def ensureOptionValue(company, branch, key, value, user=None):
        encoded_value, is_array = OptionSettingService.encodeValue(value)
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
        if option.value in [None, ""]:
            option.value = encoded_value
            option.array = is_array
            update_fields.extend(["value", "array"])
        if update_fields:
            option.save(update_fields=[*set(update_fields), "updated_at"])
        return option

    @staticmethod
    def ensureOptions(company, branch, user=None):
        from apps.payments.models import PaymentType

        payment_type = PaymentType.objects.filter(
            company_id=company.id,
            branch_id=branch.id,
            identifier="cash-payment",
            status=0,
        ).first()
        defaults = {
            **OptionSettingService.EXTRA_OPTION_DEFAULTS,
            "ns_pos_allow_decimal_quantities": "yes",
            "ns_pos_quick_product": "yes",
            "ns_pos_show_quantity": "yes",
            "ns_currency_precision": 2,
            "ns_pos_hide_empty_categories": "yes",
            "ns_pos_unit_price_ediable": "yes",
            "ns_pos_order_types": ["takeaway", "delivery"],
            "ns_pos_registers_default_change_payment_type": payment_type.id if payment_type else 1,
        }
        for key, value in defaults.items():
            OptionSettingService.ensureOptionValue(company, branch, key, value, user=user)
        return Option.objects.filter(company=company, branch=branch)

    @staticmethod
    def ensureOption(company, branch, user=None):
        return OptionSettingService.ensureOptions(company=company, branch=branch, user=user)

    @staticmethod
    def decodeOption(option):
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

    @staticmethod
    def optionValue(options):
        option_map = {option.key: option for option in options}
        defaults = OptionSettingService.defaultValues()
        values = {
            "allow_partial_orders": defaults["allow_partial_orders"],
            "enable_customer_rewards": defaults["enable_customer_rewards"],
            "enable_credit_account": defaults["enable_credit_account"],
            "enable_cash_registers": defaults["enable_cash_registers"],
        }
        reverse_map = {
            key: OptionSettingService.decodeOption(option_map.get(option_key))
            for key, option_key in OptionSettingService.OPTION_KEY_MAP.items()
        }
        values.update({key: value for key, value in reverse_map.items() if value is not None})
        return {**defaults, **values}

    @staticmethod
    def optionValueOld(option):
        try:
            data = json.loads(option.value or "{}")
        except (TypeError, json.JSONDecodeError):
            data = {}
        return {**OptionSettingService.defaultValues(), **data}

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
        settings = OptionSettingService.ensureSettings(user)
        setting_data = {
            field: OptionSettingService.optionValue(settings).get(field)
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
            if field not in OptionSettingService.OPTION_KEY_MAP:
                setting_data[field] = bool(data.get(field))
                continue
            if field == "currency_precision":
                precision = int(data.get(field, 2))
                if precision < 0 or precision > 6:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Currency precision must be between 0 and 6.")
                setting_data[field] = precision
            elif field == "default_change_payment_type":
                setting_data[field] = data.get(field) or "cash-payment"
            else:
                setting_data[field] = bool(data.get(field))
        setting_data["order_types"] = OptionSettingService.normalizeOrderTypes(data.get("order_types"))
        for field, key in OptionSettingService.OPTION_KEY_MAP.items():
            OptionSettingService.ensureOptionValue(
                user.company,
                user.branch,
                key,
                setting_data.get(field),
                user=user,
            )
        return OptionSettingService.get(user)
