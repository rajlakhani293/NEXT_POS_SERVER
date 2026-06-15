# type:ignore
from functools import wraps
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error


def get_user_permission_codenames(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return set()

    if getattr(user, "is_superuser", False):
        return {"*"}

    permissions = set(user.user_permissions.values_list("codename", flat=True))

    role_ids = set(
        user.role_relations.filter(status=0).values_list("role_id", flat=True)
    )
    if getattr(user, "role_id", None):
        role_ids.add(user.role_id)

    if role_ids:
        from apps.accounts.models import Role

        permissions.update(
            Role.objects.filter(id__in=role_ids, status=0)
            .values_list("permissions__codename", flat=True)
            .exclude(permissions__codename__isnull=True)
        )

    return permissions


def user_has_permissions(user, required_permissions, match="all"):
    effective_permissions = get_user_permission_codenames(user)
    if "*" in effective_permissions:
        return True

    required = [perm for perm in required_permissions if perm]
    if not required:
        return True

    if match == "any":
        return any(perm in effective_permissions for perm in required)
    return all(perm in effective_permissions for perm in required)


def require_permissions(request, required_permissions, match="all"):
    user = getattr(request, "user", None)
    if not user_has_permissions(user, required_permissions, match=match):
        raise api_error(
            403,
            ErrorCodes.PERMISSION_DENIED,
            "You do not have permission to perform this action.",
        )
    return True


def permission_required(*required_permissions, match="all"):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            require_permissions(request, required_permissions, match=match)
            return func(request, *args, **kwargs)

        return wrapper

    return decorator
