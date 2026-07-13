import traceback

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from ninja import NinjaAPI
from ninja.errors import HttpError, ValidationError

from apps.accounts.api import authRouter as auth_router
from apps.accounts.api import router as accounts_router
from apps.accounts.api import sourceRouter as source_accounts_router
from apps.accounting.api import router as accounting_router
from apps.accounting.api import transactionAccountsRouter as transaction_accounts_router
from apps.accounting.api import transactionsRouter as transactions_router
from apps.catalog.api import inventoryRouter as inventory_router
from apps.catalog.api import router as catalog_router
from apps.customers.api import groupsRouter as customer_groups_router
from apps.customers.api import router as customers_router
from apps.organizations.api import router as organizations_router
from apps.promotions.api import router as promotions_router
from apps.purchases.api import router as purchases_router
from apps.purchases.api import providersRouter as providers_router
from apps.purchases.api import procurementsRouter as procurements_router
from apps.registers.api import router as registers_router
from apps.reports.api import dashboardRouter as dashboard_router
from apps.reports.api import router as reports_router
from apps.rewards.api import router as rewards_router
from apps.rewards.api import sourceRouter as source_rewards_router
from apps.sales.api import ordersRouter as orders_router
from apps.sales.api import router as sales_router
from apps.settings.api import paymentsRouter as payments_router
from apps.settings.api import router as settings_router
from apps.settings.api import sourceMediaRouter as source_media_router
from apps.settings.api import sourceNotificationsRouter as source_notifications_router
from apps.expenses.api import router as expenses_router
from apps.common.responses import errorResponse, successResponse
from apps.common.api import router as platform_router


api = NinjaAPI(title="Retail POS API", version="1.0.0")

api.add_router("/accounts/", accounts_router)
api.add_router("/auth/", auth_router)
api.add_router("/", source_accounts_router)
api.add_router("/", platform_router)
api.add_router("/", catalog_router, url_name_prefix="source_catalog")
api.add_router("/accounting/", accounting_router)
api.add_router("/transactions/", transactions_router)
api.add_router("/transactions-accounts/", transaction_accounts_router)
api.add_router("/organizations/", organizations_router)
api.add_router("/customers/", customers_router)
api.add_router("/customers-groups/", customer_groups_router)
api.add_router("/catalog/", catalog_router, url_name_prefix="catalog")
api.add_router("/inventory/", inventory_router)
api.add_router("/purchases/", purchases_router)
api.add_router("/providers/", providers_router)
api.add_router("/procurements/", procurements_router)
api.add_router("/orders/", orders_router)
api.add_router("/sales/", sales_router)
api.add_router("/registers/", registers_router, url_name_prefix="registers")
api.add_router("/cash-registers/", registers_router, url_name_prefix="source_registers")
api.add_router("/promotions/", promotions_router)
api.add_router("/rewards/", rewards_router)
api.add_router("/reward-system/", source_rewards_router)
api.add_router("/reports/", reports_router)
api.add_router("/dashboard/", dashboard_router)
api.add_router("/settings/", settings_router)
api.add_router("/payments/", payments_router)
api.add_router("/medias/", source_media_router)
api.add_router("/notifications/", source_notifications_router)
api.add_router("/expenses/", expenses_router)


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


def normalize_unique_field_name(raw_field):
    field_name = str(raw_field or "").strip("` '\"()[]{}")
    field_name = field_name.split(".")[-1]
    for suffix in ["_uniq", "_unique", "_key"]:
        field_name = field_name.removesuffix(suffix)
    if field_name.endswith("_id"):
        field_name = field_name[:-3]
    return field_name or "value"


def parse_unique_constraint_fields(message):
    lower_message = message.lower()
    tenant_fields = {"branch", "branch_id", "company", "company_id", "user", "user_id"}

    if "unique constraint failed:" in lower_message:
        raw_fields = message.split(":", 1)[-1].split(",")
        fields = [normalize_unique_field_name(field) for field in raw_fields]
        fields = [field for field in fields if field not in tenant_fields]
        if fields:
            return fields[-1]

    if "key (" in lower_message:
        raw_fields = lower_message.split("key (", 1)[1].split(")", 1)[0].split(",")
        fields = [normalize_unique_field_name(field) for field in raw_fields]
        fields = [field for field in fields if field not in tenant_fields]
        if fields:
            return fields[-1]

    return "value"


def parse_integrity_error(exc: IntegrityError):
    message = str(exc)
    lower_message = message.lower()

    if "foreign key constraint fails" in lower_message:
        field_name = "related record"
        if "foreign key (`" in lower_message:
            field_name = message.split("FOREIGN KEY (`", 1)[1].split("`", 1)[0]
        elif "foreign key (" in lower_message:
            field_name = message.split("FOREIGN KEY (", 1)[1].split(")", 1)[0]
        field_name = normalize_unique_field_name(field_name)
        label = humanize_db_field(field_name)
        return f"Invalid {label} selected.", {"field": field_name}

    if "duplicate entry" in lower_message or "unique constraint" in lower_message:
        field_name = parse_unique_constraint_fields(message)
        label = humanize_db_field(field_name).lower()
        return f"This {label} already exists.", {"field": field_name}

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
