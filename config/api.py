from django.core.exceptions import ValidationError as DjangoValidationError
from ninja import NinjaAPI
from ninja.errors import HttpError, ValidationError

from apps.accounts.api import router as accounts_router
from apps.audit.api import router as audit_router
from apps.catalog.api import router as catalog_router
from apps.customers.api import router as customers_router
from apps.expenses.api import router as expenses_router
from apps.inventory.api import router as inventory_router
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
api.add_router("/organizations/", organizations_router)
api.add_router("/customers/", customers_router)
api.add_router("/catalog/", catalog_router)
api.add_router("/inventory/", inventory_router)
api.add_router("/purchases/", purchases_router)
api.add_router("/sales/", sales_router)
api.add_router("/payments/", payments_router)
api.add_router("/registers/", registers_router)
api.add_router("/promotions/", promotions_router)
api.add_router("/rewards/", rewards_router)
api.add_router("/expenses/", expenses_router)
api.add_router("/reports/", reports_router)
api.add_router("/audit/", audit_router)
api.add_router("/settings/", settings_router)


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
    payload = errorResponse(
        "Validation failed.",
        data={"errors": exc.errors},
    )
    return api.create_response(request, payload.dict(), status=422)


@api.exception_handler(DjangoValidationError)
def django_validation_error_handler(request, exc: DjangoValidationError):
    payload = errorResponse(
        "Validation failed.",
        data={"errors": exc.messages},
    )
    return api.create_response(request, payload.dict(), status=422)


@api.exception_handler(Exception)
def generic_error_handler(request, exc: Exception):
    payload = errorResponse("Something went wrong on the server.")
    return api.create_response(request, payload.dict(), status=500)


@api.get("/health")
def health(request):
    return successResponse("Service is healthy.", data={"status": "ok"})
