# type: ignore
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.utils.text import slugify

def getAuthContext(request):
    if request is None:
        return {}

    auth = getattr(request, "auth", None)
    user = getattr(request, "user", None)

    ctx = {}

    if isinstance(auth, dict):
        ctx.update(auth)

    if user is not None and getattr(user, "is_authenticated", False):
        ctx.setdefault("user_id", getattr(user, "id", None))
        ctx.setdefault("company_id", getattr(user, "company_id", None))
        ctx.setdefault("branch_id", getattr(user, "branch_id", None))

    return ctx


def jsonsafe(value):
    if isinstance(value, dict):
        return {k: jsonsafe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonsafe(item) for item in value]
    if isinstance(value, tuple):
        return [jsonsafe(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def decimalValue(value):
    return Decimal(str(value or 0))


def serializeModelInstance(instance):
    if instance is None:
        return None

    if isinstance(instance, dict):
        return jsonsafe(instance)

    if not hasattr(instance, "_meta"):
        raise ImproperlyConfigured("serializeModelInstance expects a Django model instance or dict.")

    data = {}

    for field in instance._meta.fields:
        if field.primary_key:
            data[field.name] = getattr(instance, field.attname)
        elif field.is_relation:
            data[field.attname] = getattr(instance, field.attname)
        else:
            data[field.name] = getattr(instance, field.name)

    return jsonsafe(data)


def validateUniqueFields(
    model,
    fields,
    request=None,
    scope="branch",
    exclude_id=None,
    case_insensitive=None,
    status_in=(0, 1),
    messages=None,
    extra_filters=None,
):
    from apps.common.error_codes import ErrorCodes
    from apps.common.exceptions import api_error

    query = model.objects.all()
    auth_context = getAuthContext(request)
    case_insensitive = set(case_insensitive or [])
    messages = messages or {}

    if scope == "branch":
        query = query.filter(
            company_id=auth_context.get("company_id"),
            branch_id=auth_context.get("branch_id"),
        )
    elif scope == "company":
        query = query.filter(company_id=auth_context.get("company_id"))
    elif scope not in (None, "global"):
        raise ImproperlyConfigured("validateUniqueFields scope must be branch, company, global, or None.")

    if status_in is not None:
        query = query.filter(status__in=status_in)
    if extra_filters:
        query = query.filter(**extra_filters)
    if exclude_id:
        query = query.exclude(id=exclude_id)

    for field_name, value in (fields or {}).items():
        if value in (None, ""):
            continue
        lookup = f"{field_name}__iexact" if field_name in case_insensitive else field_name
        if query.filter(**{lookup: value}).exists():
            label = field_name.replace("_", " ").title()
            raise api_error(
                400,
                ErrorCodes.BAD_REQUEST,
                messages.get(field_name) or f"{label} already exists.",
            )


def validateTenantRelationIds(
    model,
    ids,
    request=None,
    label=None,
    tenant_config=True,
    required=False,
    status_in=None,
):
    from apps.common.commonQuery import commonQuery
    from apps.common.error_codes import ErrorCodes
    from apps.common.exceptions import api_error

    raw_ids = ids if isinstance(ids, (list, tuple, set)) else [ids]
    normalized_ids = []
    for item_id in raw_ids:
        if item_id in (None, ""):
            continue
        try:
            normalized_id = int(item_id)
        except (TypeError, ValueError):
            raise api_error(
                400,
                ErrorCodes.BAD_REQUEST,
                f"Invalid {label or model._meta.verbose_name.title()} selected.",
            )
        if normalized_id > 0:
            normalized_ids.append(normalized_id)

    unique_ids = list(dict.fromkeys(normalized_ids))
    relation_label = label or model._meta.verbose_name.title()

    if required and not unique_ids:
        raise api_error(400, ErrorCodes.BAD_REQUEST, f"{relation_label} is required.")
    if not unique_ids:
        return []

    filters = {"id__in": unique_ids}
    model_field_names = {field.name for field in model._meta.get_fields()}
    if status_in is not None and "status" in model_field_names:
        filters["status__in"] = status_in

    records = commonQuery.findAllRecords(
        model,
        filters,
        {"attributes": ["id"]},
        request=request,
        tenant_config=tenant_config,
    )
    found_ids = {int(record["id"]) for record in records}
    missing_ids = [item_id for item_id in unique_ids if item_id not in found_ids]
    if missing_ids:
        raise api_error(404, ErrorCodes.NOT_FOUND, f"{relation_label} not found.")

    return unique_ids


def validateTenantRelationId(
    model,
    item_id,
    request=None,
    label=None,
    tenant_config=True,
    required=False,
    status_in=None,
):
    ids = validateTenantRelationIds(
        model,
        [item_id],
        request=request,
        label=label,
        tenant_config=tenant_config,
        required=required,
        status_in=status_in,
    )
    return ids[0] if ids else None


def buildUniqueValue(model, request, field_name, raw_value, exclude_id=None):
    from apps.common.commonQuery import commonQuery

    value = raw_value
    counter = 1

    while True:
        record = commonQuery.findOneRecord(
            model,
            {field_name: value},
            request=request,
            tenant_config=True,
        )
        if not record or (exclude_id is not None and record.get("id") == exclude_id):
            return value
        counter += 1
        value = f"{raw_value}-{counter}"


def buildCode(model, name, code, request, exclude_id=None):
    raw_code = (code or "").strip()
    raw_name = (name or "").strip()
    base = slugify(raw_code or raw_name or "item") or "item"
    if raw_code:
        validateUniqueFields(
            model,
            {"code": base},
            request=request,
            scope="branch",
            exclude_id=exclude_id,
            status_in=(0, 1),
            case_insensitive=["code"],
            messages={"code": "Code already exists."},
        )
        return base
    return buildUniqueValue(model, request, "code", base, exclude_id=exclude_id)


def buildSlug(model, name, slug, request, exclude_id=None):
    raw_slug = (slug or "").strip()
    raw_name = (name or "").strip()
    base = slugify(raw_slug or raw_name or "product") or "product"
    if raw_slug:
        validateUniqueFields(
            model,
            {"slug": base},
            request=request,
            scope="branch",
            exclude_id=exclude_id,
            status_in=(0, 1),
            case_insensitive=["slug"],
            messages={"slug": "Slug already exists."},
        )
        return base
    return buildUniqueValue(model, request, "slug", base, exclude_id=exclude_id)


def buildSku(model, name, sku, request, exclude_id=None):
    raw_sku = (sku or "").strip()
    raw_name = (name or "").strip()
    base = (slugify(raw_sku or raw_name or "item") or "item").upper()
    if raw_sku:
        validateUniqueFields(
            model,
            {"sku": base},
            request=request,
            scope="branch",
            exclude_id=exclude_id,
            status_in=(0, 1),
            case_insensitive=["sku"],
            messages={"sku": "SKU already exists."},
        )
        return base
    return buildUniqueValue(model, request, "sku", base, exclude_id=exclude_id)


def saveUploadedFile(image, request, folder):
    if not image:
        return None
    storage = FileSystemStorage(
        location=settings.UPLOAD_ROOT,
        base_url=settings.UPLOAD_URL,
    )
    file_path = storage.save(f"{folder}/{image.name}", image)
    return request.build_absolute_uri(storage.url(file_path))


def saveProductImage(image, request):
    return saveUploadedFile(image, request, "product")


def saveCompanyLogo(image, request):
    return saveUploadedFile(image, request, "company-logo")
