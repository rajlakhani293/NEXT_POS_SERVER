# type: ignore
from apps.common.responses import successResponse
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.settingsapi.models import BusinessSetting


ORDER_TYPE_OPTIONS = [
    {"value": "take_order", "label": "Take Order"},
    {"value": "delivery", "label": "Delivery"},
]


BUSINESS_SETTING_FIELDS = [
    "allow_partial_orders",
    "enable_customer_rewards",
    "enable_credit_account",
    "enable_cash_registers",
    "order_types",
]


class BusinessSettingService:
    @staticmethod
    def defaultValues():
        return {
            "allow_partial_orders": False,
            "enable_customer_rewards": False,
            "enable_credit_account": False,
            "enable_cash_registers": True,
            "order_types": ["take_order", "delivery"],
        }

    @staticmethod
    def ensureCompanySettings(company):
        settings, _created = BusinessSetting.objects.get_or_create(
            company_id=company.id,
            defaults=BusinessSettingService.defaultValues(),
        )
        return settings

    @staticmethod
    def ensureSettings(user):
        settings, _created = BusinessSetting.objects.get_or_create(
            company_id=user.company_id,
            defaults=BusinessSettingService.defaultValues(),
        )
        return settings

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
        data = BusinessSettingService.buildSessionSettings(user)
        return successResponse(
            "Business settings retrieved successfully.",
            data=data,
        )

    @staticmethod
    def buildSessionSettings(user):
        settings = BusinessSettingService.ensureSettings(user)
        setting_data = {field: getattr(settings, field) for field in BUSINESS_SETTING_FIELDS}
        if not setting_data["order_types"]:
            setting_data["order_types"] = ["take_order", "delivery"]
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
        settings = BusinessSettingService.ensureSettings(user)
        for field in BUSINESS_SETTING_FIELDS:
            if field == "order_types":
                continue
            setattr(settings, field, bool(data.get(field)))
        settings.order_types = BusinessSettingService.normalizeOrderTypes(data.get("order_types"))
        settings.save()
        return BusinessSettingService.get(user)
