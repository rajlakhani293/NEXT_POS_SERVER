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
    OPTION_KEY = "business_settings"

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
        for branch in company.branches.all():
            OptionSettingService.ensureOption(company=company, branch=branch)
        return OptionSettingService.defaultValues()

    @staticmethod
    def ensureSettings(user):
        return OptionSettingService.ensureOption(
            company=user.company,
            branch=user.branch,
            user=user,
        )

    @staticmethod
    def ensureOption(company, branch, user=None):
        option, created = Option.objects.get_or_create(
            company=company,
            branch=branch,
            key=OptionSettingService.OPTION_KEY,
            defaults={
                "user": user,
                "value": json.dumps(OptionSettingService.defaultValues()),
                "array": True,
            },
        )
        if user and option.user_id is None:
            option.user = user
            option.save(update_fields=["user"])
        if created:
            return option
        return option

    @staticmethod
    def optionValue(option):
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
        settings = OptionSettingService.ensureSettings(user)
        setting_data = OptionSettingService.optionValue(settings)
        for field in BUSINESS_SETTING_FIELDS:
            if field == "order_types":
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
        settings.value = json.dumps(setting_data)
        settings.array = True
        settings.save(update_fields=["value", "array", "updated_at"])
        return OptionSettingService.get(user)
