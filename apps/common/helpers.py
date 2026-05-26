from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ImproperlyConfigured

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
