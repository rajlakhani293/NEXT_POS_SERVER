# type: ignore
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import serializeModelInstance, validateUniqueFields
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
from apps.settings.models import Media, Notification, PaymentType, paymentTypeValues


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


class PaymentTypeService:
    @staticmethod
    def normalizeIdentifier(identifier: str, label: str):
        return slugify(identifier or label)

    @staticmethod
    def ensureDefaultPaymentTypes(company, branch):
        seeded = []
        for item in DEFAULT_PAYMENT_TYPES:
            payment_type, created = PaymentType.objects.get_or_create(
                company_id=company.id,
                branch_id=branch.id,
                identifier=item["identifier"],
                defaults={
                    "label": item["label"],
                    "description": item["description"],
                    "readonly": True,
                    "sort_order": item["sort_order"],
                    "status": 0,
                },
            )
            update_fields = []
            if not payment_type.readonly:
                payment_type.readonly = True
                update_fields.append("readonly")
            if payment_type.sort_order != item["sort_order"] and created:
                payment_type.sort_order = item["sort_order"]
                update_fields.append("sort_order")
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

        payment_type = PaymentType.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            identifier=normalized,
            status=0,
        ).first()
        if payment_type is None:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid payment type.")
        return payment_type.identifier

    @staticmethod
    def dropdownList(request):
        items = (
            PaymentType.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                status=0,
            )
            .order_by("sort_order", "label")
            .values("identifier", "label")
        )
        return successResponse(
            "Payment types retrieved successfully.",
            data=[{"value": item["identifier"], "label": item["label"]} for item in items],
        )

    @staticmethod
    def listPaymentTypes(data, request):
        field_config = [["label", True, True], ["identifier", True, True], ["description", True, False]]
        return commonQuery.fetchPaginatedData(
            PaymentType,
            data,
            field_config,
            {
                "attributes": ["id", "label", "identifier", "description", "readonly", "sort_order", "status"],
                "order": ["sort_order", "label"],
            },
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )

    @staticmethod
    def createPaymentType(data, request):
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
                **data,
                "identifier": identifier,
                "readonly": False,
                "sort_order": max(int(data.get("sort_order") or 0), 0),
            },
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        return successResponse("Payment type created successfully.", data=payment_type)

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
        return payment_type

    @staticmethod
    def updatePaymentType(payment_type_id, data, request):
        with transaction.atomic():
            payment_type = PaymentType.objects.filter(
                id=payment_type_id,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                status__in=[0, 1],
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
                    **data,
                    "identifier": identifier,
                    "readonly": payment_type.readonly,
                    "sort_order": max(int(data.get("sort_order") or 0), 0),
                },
                request=request,
                tenant_config={"company_id": True, "branch_id": True},
            )
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")
            return updated

    @staticmethod
    def deletePaymentTypes(data, request):
        ids = data.get("ids") or []
        ids = ids if isinstance(ids, list) else [ids]
        if PaymentType.objects.filter(
            id__in=ids,
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            readonly=True,
        ).exists():
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Default payment types cannot be deleted.")
        count = commonQuery.softDeleteById(
            PaymentType,
            ids,
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Payment type not found.")
        return {"deleted_count": count}

    @staticmethod
    def updatePaymentTypeStatus(data, request):
        status = data.get("status")
        ids = data.get("ids") or []
        ids = ids if isinstance(ids, list) else [ids]
        if PaymentType.objects.filter(
            id__in=ids,
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            readonly=True,
        ).exists():
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
    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    MAX_FILE_SIZE = 5 * 1024 * 1024

    @staticmethod
    def upload(file, request, folder="general", entity_type="", entity_id=None, alt_text=""):
        if not file:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "File is required.")
        if getattr(file, "size", 0) > MediaService.MAX_FILE_SIZE:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "File size must be 5MB or less.")
        content_type = getattr(file, "content_type", "") or ""
        if content_type and content_type not in MediaService.ALLOWED_IMAGE_TYPES:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Only image files are allowed.")

        storage = FileSystemStorage(location=settings.UPLOAD_ROOT, base_url=settings.UPLOAD_URL)
        saved_path = storage.save(f"{folder}/{file.name}", file)
        path = Path(saved_path)
        media = commonQuery.createRecord(
            Media,
            {
                "name": path.name,
                "extension": path.suffix.lstrip("."),
                "slug": f"{path.stem}-{uuid4().hex[:8]}",
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Media uploaded successfully.", data=media)

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
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Media retrieved successfully.", data=result)

    @staticmethod
    def update(media_id, data, request):
        data = {key: value for key, value in data.items() if key in ["name", "extension", "slug"]}
        updated = commonQuery.updateRecordById(Media, media_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Media not found.")
        return successResponse("Media updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Media, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Media not found.")
        return successResponse("Media deleted successfully.")


class NotificationService:
    @staticmethod
    def create(data, request):
        data["description"] = data.get("description") or data.pop("message", "")
        data["source"] = data.get("source") or data.pop("source_type", "system")
        data["url"] = data.get("url") or data.pop("action_url", "#")
        data["actions"] = data.get("actions") or data.pop("payload", None)
        data["identifier"] = data.get("identifier") or f"notification-{timezone.now().timestamp()}"
        notification = commonQuery.createRecord(Notification, data, request=request, tenant_config=True)
        return successResponse("Notification created successfully.", data=notification)

    @staticmethod
    def push(*, title, message="", notification_type="info", source_type="system", source_id=None, user_id=None, action_url="", payload=None, request=None):
        return commonQuery.createRecord(
            Notification,
            {
                "user_id": user_id,
                "identifier": f"{source_type}-{source_id or 'general'}",
                "title": title,
                "description": message,
                "source": source_type,
                "url": action_url or "#",
                "actions": payload,
            },
            request=request,
            tenant_config=True,
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
        count = Notification.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
        ).filter(user_id__in=[request.user.id, None]).count()
        return successResponse("Unread notification count retrieved successfully.", data={"count": count})

    @staticmethod
    def markRead(data, request):
        ids = data.get("ids")
        if not isinstance(ids, list):
            ids = [ids]
        count = Notification.objects.filter(
            id__in=ids,
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            status__in=[0, 1],
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
