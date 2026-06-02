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
    return buildUniqueValue(model, request, "code", base, exclude_id=exclude_id)


def buildSlug(model, name, slug, request, exclude_id=None):
    raw_slug = (slug or "").strip()
    raw_name = (name or "").strip()
    base = slugify(raw_slug or raw_name or "product") or "product"
    return buildUniqueValue(model, request, "slug", base, exclude_id=exclude_id)


def buildSku(model, name, sku, request, exclude_id=None):
    raw_sku = (sku or "").strip()
    raw_name = (name or "").strip()
    base = (slugify(raw_sku or raw_name or "item") or "item").upper()
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
