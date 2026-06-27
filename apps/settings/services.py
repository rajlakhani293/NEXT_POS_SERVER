# type: ignore
import datetime
import json
import time
from pathlib import Path
from types import SimpleNamespace
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db import connection
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import Role, User
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
from apps.organizations.models import Branch
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
        "store_name",
        "scale_barcode_prefix",
        "scale_barcode_type",
        "orders_code_type",
        "orders_quotation_expiration",
        "pos_tax_group",
        "pos_tax_type",
    }
    INTEGER_SETTING_FIELDS = {
        "currency_precision",
        "scale_barcode_product_length",
        "scale_barcode_value_length",
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
    ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]
    MAX_FILE_SIZE = 5 * 1024 * 1024

    @staticmethod
    def mediaData(media):
        data = serializeModelInstance(media)
        original_path = f"{media.slug}.{media.extension}"
        data["sizes"] = {
            "original": f"{settings.UPLOAD_URL}{original_path}",
        }
        return data

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
        if content_type and content_type not in MediaService.ALLOWED_IMAGE_TYPES:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Only image files are allowed.")

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
        ids = data.get("ids")
        ids = ids if isinstance(ids, list) else [ids]
        media_items = commonQuery.branchScopedQueryset(Media, {"id__in": ids, "status__in": [0, 1]}, request)
        storage = FileSystemStorage(location=settings.UPLOAD_ROOT, base_url=settings.UPLOAD_URL)
        for media in media_items:
            storage.delete(f"{media.slug}.{media.extension}")

        count = commonQuery.softDeleteById(Media, ids, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Media not found.")
        return successResponse("Media deleted successfully.")


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
