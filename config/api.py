import traceback

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from ninja import NinjaAPI
from ninja.errors import HttpError, ValidationError

from apps.accounts.api import router as accounts_router
from apps.accounting.api import router as accounting_router
from apps.catalog.api import router as catalog_router
from apps.customers.api import router as customers_router
from apps.expenses.api import router as expenses_router
from apps.inventory.api import router as inventory_router
from apps.mediahub.api import router as media_router
from apps.notifications.api import router as notifications_router
from apps.organizations.api import router as organizations_router
from apps.payments.api import router as payments_router
from apps.promotions.api import router as promotions_router
from apps.purchases.api import router as purchases_router
from apps.registers.api import router as registers_router
from apps.reports.api import router as reports_router
from apps.rewards.api import router as rewards_router
from apps.sales.api import router as sales_router
from apps.settingsapi.api import router as settings_router
from apps.common.responses import errorResponse, successResponse


api = NinjaAPI(title="Retail POS API", version="1.0.0")

api.add_router("/accounts/", accounts_router)
api.add_router("/accounting/", accounting_router)
api.add_router("/organizations/", organizations_router)
api.add_router("/customers/", customers_router)
api.add_router("/catalog/", catalog_router)
api.add_router("/inventory/", inventory_router)
api.add_router("/media/", media_router)
api.add_router("/notifications/", notifications_router)
api.add_router("/purchases/", purchases_router)
api.add_router("/sales/", sales_router)
api.add_router("/payments/", payments_router)
api.add_router("/registers/", registers_router)
api.add_router("/promotions/", promotions_router)
api.add_router("/rewards/", rewards_router)
api.add_router("/expenses/", expenses_router)
api.add_router("/reports/", reports_router)
api.add_router("/settings/", settings_router)


def format_validation_errors(errors):
    formatted = {}

    for err in errors:
        loc = err.get("loc") or []
        field_name = next((part for part in reversed(loc) if isinstance(part, str) and part not in ["body", "payload", "query", "path"]), None)
        if not field_name:
            field_name = "non_field_error"

        err_type = err.get("type", "")
        message = err.get("msg", "Invalid value.")

        if err_type == "missing":
            message = f"{field_name} is required."

        formatted.setdefault(field_name, [])
        if message not in formatted[field_name]:
            formatted[field_name].append(message)

    return formatted


def humanize_db_field(field_name):
    field_name = str(field_name or "").strip("` ")
    if field_name.endswith("_id"):
        field_name = field_name[:-3]
    return field_name.replace("_", " ").title() or "Related record"


def parse_integrity_error(exc: IntegrityError):
    message = str(exc)
    lower_message = message.lower()

    if "foreign key constraint fails" in lower_message:
        field_name = "related record"
        if "foreign key (`" in lower_message:
            field_name = message.split("FOREIGN KEY (`", 1)[1].split("`", 1)[0]
        elif "foreign key (" in lower_message:
            field_name = message.split("FOREIGN KEY (", 1)[1].split(")", 1)[0]
        label = humanize_db_field(field_name)
        return f"Invalid {label} selected.", {"field": field_name}

    if "duplicate entry" in lower_message or "unique constraint" in lower_message:
        field_name = "value"
        if " for key " in lower_message:
            field_name = message.rsplit(" for key ", 1)[-1].strip("'\"() ")
            field_name = field_name.split(".")[-1]
            for suffix in ["_uniq", "_unique", "_key"]:
                field_name = field_name.removesuffix(suffix)
        return "This record already exists.", {"field": field_name}

    return "Database validation failed.", None


@api.exception_handler(HttpError)
def http_error_handler(request, exc: HttpError):
    message = str(exc.message)
    data = None

    if isinstance(exc.message, dict):
        message = exc.message.get("message", message)
        data = exc.message.get("data")

    payload = errorResponse(message, data=data)
    return api.create_response(request, payload.dict(), status=exc.status_code)


@api.exception_handler(ValidationError)
def validation_error_handler(request, exc: ValidationError):
    formatted_errors = format_validation_errors(exc.errors)
    payload = errorResponse(
        "Validation failed.",
        data={"errors": formatted_errors},
    )
    return api.create_response(request, payload.dict(), status=422)


@api.exception_handler(DjangoValidationError)
def django_validation_error_handler(request, exc: DjangoValidationError):
    payload = errorResponse(
        "Validation failed.",
        data={"errors": exc.messages},
    )
    return api.create_response(request, payload.dict(), status=422)


@api.exception_handler(IntegrityError)
def integrity_error_handler(request, exc: IntegrityError):
    if settings.DEBUG:
        traceback.print_exc()
    message, data = parse_integrity_error(exc)
    payload = errorResponse(message, data=data)
    return api.create_response(request, payload.dict(), status=400)


@api.exception_handler(Exception)
def generic_error_handler(request, exc: Exception):
    if settings.DEBUG:
        traceback.print_exc()
    payload = errorResponse("Something went wrong on the server.")
    return api.create_response(request, payload.dict(), status=500)


@api.get("/health")
def health(request):
    return successResponse("Service is healthy.", data={"status": "ok"})
