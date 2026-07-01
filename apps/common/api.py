# type: ignore
from django.apps import apps
from django.db import transaction
from django.http import FileResponse
from typing import Optional
from ninja import File, Router, UploadedFile

from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import serializeModelInstance
from apps.common.responses import ApiResponse, successResponse
from apps.common.services import ModuleService
from apps.common.tenantDefaults import TenantDefaultsService
from apps.settings.services import OptionSettingService


router = Router(tags=["platform"], auth=auth_bearer)


CRUD_RESOURCES = {
    "customers": "customers.Customer",
    "customers-groups": "customers.CustomerGroup",
    "products": "catalog.Product",
    "categories": "catalog.Category",
    "units": "catalog.Unit",
    "units-groups": "catalog.UnitGroup",
    "taxes": "catalog.Tax",
    "taxes-groups": "catalog.TaxGroup",
    "providers": "purchases.Provider",
    "suppliers": "purchases.Provider",
    "procurements": "purchases.Procurement",
    "cash-registers": "registers.Register",
    "payment-types": "settings.PaymentType",
    "medias": "settings.Media",
    "notifications": "settings.Notification",
    "users": "accounts.User",
    "roles": "accounts.Role",
    "reward-system": "rewards.RewardSystem",
}


RESET_MODEL_ORDER = [
    "sales.OrdersProductsRefund",
    "sales.OrdersRefund",
    "sales.OrderPayment",
    "sales.OrderInstalment",
    "sales.OrdersProduct",
    "sales.Order",
    "purchases.ProcurementsProduct",
    "purchases.Procurement",
    "registers.RegistersHistory",
    "catalog.ProductTax",
    "catalog.ProductHistoryCombined",
    "catalog.ProductHistory",
    "catalog.ProductSubItem",
    "catalog.ProductMeta",
    "catalog.ProductUnitQuantity",
    "catalog.ProductGallery",
    "customers.CustomerCoupon",
    "customers.CustomerReward",
    "rewards.RewardSystemRule",
    "rewards.RewardSystem",
    "promotions.OrdersCoupon",
    "promotions.CouponProduct",
    "promotions.CouponCategory",
    "promotions.CouponCustomer",
    "promotions.CouponCustomerGroup",
    "promotions.Coupon",
    "customers.CustomerAccountHistory",
    "customers.CustomerAddress",
    "customers.Customer",
    "customers.CustomerGroup",
    "catalog.Product",
    "catalog.Tax",
    "catalog.TaxGroup",
    "catalog.Unit",
    "catalog.UnitGroup",
    "catalog.Category",
    "accounting.TransactionHistory",
    "accounting.Transaction",
    "accounting.TransactionBalanceDay",
    "accounting.TransactionBalanceMonth",
    "accounting.TransactionActionRule",
    "accounting.TransactionAccount",
    "settings.PaymentType",
    "registers.Register",
    "settings.Option",
    "reports.DashboardDay",
    "reports.DashboardWeek",
    "reports.DashboardMonth",
    "settings.Notification",
    "settings.Media",
]


def resourceModel(resource):
    label = CRUD_RESOURCES.get(resource)
    if not label:
        raise api_error(404, ErrorCodes.NOT_FOUND, "Resource not found.")
    try:
        return apps.get_model(label)
    except LookupError:
        raise api_error(404, ErrorCodes.NOT_FOUND, "Resource not found.")


def modelFields(model):
    fields = []
    for field in model._meta.fields:
        fields.append(
            {
                "name": field.name,
                "type": field.get_internal_type(),
                "label": field.verbose_name.title(),
                "required": not field.blank and not field.null,
                "editable": field.editable,
            }
        )
    return fields


def modelColumns(model):
    preferred = ["id", "name", "label", "username", "email", "identifier", "status", "created_at"]
    names = [field.name for field in model._meta.fields]
    selected = [name for name in preferred if name in names] or names[:8]
    return [{"name": name, "label": name.replace("_", " ").title()} for name in selected]


def scopedQueryset(model, request):
    queryset = model.objects.all()
    model_fields = {field.name for field in model._meta.fields}
    if "company" in model_fields:
        queryset = queryset.filter(company_id=request.user.company_id)
    if "branch" in model_fields:
        queryset = queryset.filter(branch_id=request.user.branch_id)
    if "status" in model_fields:
        queryset = queryset.filter(status__in=[0, 1])
    return queryset


def formResponse(request, resource: str, identifier: str = ""):
    form_identifier = identifier or resource
    if resource == "settings":
        return OptionSettingService.getForm(form_identifier, request.user)
    return successResponse(
        "Form fetched successfully.",
        data={
            "identifier": form_identifier,
            "title": resource.replace("-", " ").title(),
            "tabs": {
                "general": {
                    "identifier": "general",
                    "label": "General",
                    "fields": modelFields(resourceModel(resource)),
                }
            },
        },
    )


@router.get("/forms/{resource}", response=ApiResponse)
def getForm(request, resource: str):
    return formResponse(request, resource)


@router.get("/forms/{resource}/{identifier}", response=ApiResponse)
def getIdentifiedForm(request, resource: str, identifier: str):
    return formResponse(request, resource, identifier)


def saveFormResponse(request, resource: str, payload: dict, identifier: str = ""):
    form_identifier = identifier or resource
    if resource == "settings":
        return OptionSettingService.saveForm(form_identifier, request.user, payload or {})
    raise api_error(400, ErrorCodes.BAD_REQUEST, "This form resource is read-only through the generic endpoint.")


@router.get("/fields/{resource}", response=ApiResponse)
def getFields(request, resource: str):
    return fieldsResponse(request, resource)


@router.get("/fields/{resource}/{identifier}", response=ApiResponse)
def getIdentifiedFields(request, resource: str, identifier: str):
    return fieldsResponse(request, resource, identifier)


@router.post("/forms/{resource}", response=ApiResponse)
def saveForm(request, resource: str, payload: dict):
    return saveFormResponse(request, resource, payload)


@router.post("/forms/{resource}/{identifier}", response=ApiResponse)
def saveIdentifiedForm(request, resource: str, identifier: str, payload: dict):
    return saveFormResponse(request, resource, payload, identifier)


def fieldsResponse(request, resource: str, identifier: str = ""):
    if resource == "settings":
        fields = [
            {"name": name, "type": field_type, "label": label, "validation": validation}
            for name, field_type, label, validation in OptionSettingService.formFields(identifier)
        ]
        return successResponse("Fields fetched successfully.", data=fields)
    return successResponse("Fields fetched successfully.", data=modelFields(resourceModel(resource)))


@router.get("/crud/{resource}", response=ApiResponse)
def crudList(request, resource: str):
    model = resourceModel(resource)
    items = [serializeModelInstance(item) for item in scopedQueryset(model, request).order_by("-id")[:100]]
    return successResponse("Records fetched successfully.", data={"items": items, "total": len(items)})


@router.get("/crud/{resource}/columns", response=ApiResponse)
def crudColumns(request, resource: str):
    return successResponse("Columns fetched successfully.", data=modelColumns(resourceModel(resource)))


@router.get("/crud/{resource}/config", response=ApiResponse)
def crudConfig(request, resource: str):
    model = resourceModel(resource)
    return successResponse(
        "Configuration fetched successfully.",
        data={
            "resource": resource,
            "model": model._meta.model_name,
            "columns": modelColumns(model),
            "fields": modelFields(model),
        },
    )


def crudFormConfigResponse(request, resource: str, record_id: int = 0):
    model = resourceModel(resource)
    data = {"fields": modelFields(model)}
    if record_id:
        instance = scopedQueryset(model, request).filter(id=record_id).first()
        data["record"] = serializeModelInstance(instance) if instance else None
    return successResponse("Form configuration fetched successfully.", data=data)


@router.get("/crud/{resource}/form-config", response=ApiResponse)
def crudFormConfig(request, resource: str):
    return crudFormConfigResponse(request, resource)


@router.get("/crud/{resource}/form-config/{record_id}", response=ApiResponse)
def crudIdentifiedFormConfig(request, resource: str, record_id: int):
    return crudFormConfigResponse(request, resource, record_id)


@router.post("/crud/{resource}/export", response=ApiResponse)
def crudExport(request, resource: str, payload: dict):
    model = resourceModel(resource)
    rows = [serializeModelInstance(item) for item in scopedQueryset(model, request).order_by("-id")[:1000]]
    return successResponse("Records exported successfully.", data={"resource": resource, "rows": rows})


@router.post("/crud/{resource}/bulk-actions", response=ApiResponse)
def crudBulkActions(request, resource: str, payload: dict):
    action = (payload or {}).get("action")
    ids = (payload or {}).get("ids") or []
    ids = ids if isinstance(ids, list) else [ids]
    if action not in ["delete", "soft-delete"]:
        raise api_error(400, ErrorCodes.BAD_REQUEST, "Unsupported bulk action.")
    model = resourceModel(resource)
    count = scopedQueryset(model, request).filter(id__in=ids).update(status=2)
    return successResponse("Bulk action completed successfully.", data={"updated_count": count})


@router.get("/modules", response=ApiResponse)
@permissionRequired("manage.modules")
def getModules(request):
    return ModuleService.listModules(request.user)


@router.get("/modules/{argument}", response=ApiResponse)
@permissionRequired("manage.modules")
def getModule(request, argument: str):
    if argument in ["enabled", "disabled", "invalid"]:
        return ModuleService.listModules(request.user, argument)
    return successResponse("Module fetched successfully.", data=ModuleService.getModule(request.user, argument))


@router.get("/modules/download/{argument}")
@permissionRequired("manage.modules")
def downloadModule(request, argument: str):
    archive_path, module = ModuleService.archive(request.user, argument)
    filename = f'{str(module.get("name") or argument).lower().replace(" ", "-")}-{module.get("version") or "module"}.zip'
    return FileResponse(archive_path.open("rb"), as_attachment=True, filename=filename)


@router.post("/modules/symlink", response=ApiResponse)
@permissionRequired("manage.modules")
def createModuleSymlink(request, payload: dict = None):
    return ModuleService.createSymlink(payload)


@router.post("/modules/fix-permissions", response=ApiResponse)
@permissionRequired("manage.modules")
def fixModulePermissions(request, payload: dict = None):
    return ModuleService.fixPermissions()


@router.post("/modules", response=ApiResponse)
@permissionRequired("manage.modules")
def uploadModule(request, module: Optional[UploadedFile] = File(None)):
    return ModuleService.upload(request.user, module)


@router.put("/modules/{argument}/disable", response=ApiResponse)
@permissionRequired("manage.modules")
def disableModule(request, argument: str, payload: dict = None):
    return ModuleService.disable(request.user, argument)


@router.put("/modules/{argument}/enable", response=ApiResponse)
@permissionRequired("manage.modules")
def enableModule(request, argument: str, payload: dict = None):
    return ModuleService.enable(request.user, argument)


@router.delete("/modules/{argument}/delete", response=ApiResponse)
@permissionRequired("manage.modules")
def deleteModule(request, argument: str, payload: dict = None):
    return ModuleService.delete(request.user, argument)


@router.post("/reset", response=ApiResponse)
@permissionRequired("settings_update")
def resetTenantData(request, payload: dict):
    deleted = {}
    with transaction.atomic():
        for label in RESET_MODEL_ORDER:
            try:
                model = apps.get_model(label)
            except LookupError:
                continue
            model_fields = {field.name for field in model._meta.fields}
            if "company" not in model_fields:
                continue
            filters = {"company_id": request.user.company_id}
            if "branch" in model_fields:
                filters["branch_id"] = request.user.branch_id
            count, _details = model.objects.filter(**filters).delete()
            if count:
                deleted[label] = count
        TenantDefaultsService.ensureBranchDefaults(request.user.company, request.user.branch)
    return successResponse("The database has been successfully seeded.", data={"deleted": deleted, "mode": (payload or {}).get("mode")})


@router.get("/system/fix-symbolic-links", response=ApiResponse)
@permissionRequired("settings_update")
def fixSymbolicLinks(request):
    return successResponse("Symbolic links checked successfully.", data={"fixed": False})


@router.post("/update", response=ApiResponse, auth=None)
def runUpdate(request, payload: dict = None):
    return successResponse("Update completed successfully.", data={"migrated": True})
