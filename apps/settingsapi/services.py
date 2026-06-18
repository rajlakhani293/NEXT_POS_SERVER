# type: ignore
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.responses import successResponse
from apps.common.tenantDefaults import (
    BUSINESS_SETTING_FIELDS,
    OPTION_KEY_MAP,
    ORDER_TYPE_OPTIONS,
    buildBusinessSettingsFromOptions,
    decodeOptionValue,
    defaultBusinessSettings,
    ensureDefaultOptions,
    ensureOptionValue,
)


class OptionSettingService:
    OPTION_KEY_MAP = OPTION_KEY_MAP

    @staticmethod
    def defaultValues():
        return defaultBusinessSettings()

    @staticmethod
    def ensureCompanySettings(company):
        return OptionSettingService.defaultValues()

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
    def ensureOptions(company, branch, user=None):
        return ensureDefaultOptions(company=company, branch=branch, user=user)

    @staticmethod
    def ensureOption(company, branch, user=None):
        return OptionSettingService.ensureOptions(company=company, branch=branch, user=user)

    @staticmethod
    def decodeOption(option):
        return decodeOptionValue(option)

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
            if field not in OPTION_KEY_MAP:
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
        for field, key in OPTION_KEY_MAP.items():
            ensureOptionValue(
                user.company,
                user.branch,
                key,
                setting_data.get(field),
                user=user,
            )
        return OptionSettingService.get(user)
