# type:ignore
from functools import wraps
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error


def getUserPermissionCodenames(user):
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
        from apps.common.commonQuery import commonQuery

        permissions.update(
            commonQuery.scopedQueryset(Role, {"id__in": role_ids, "status": 0}, tenant_config={})
            .values_list("permissions__codename", flat=True)
            .exclude(permissions__codename__isnull=True)
        )

    from apps.accounts.permission_catalog import PERMISSION_ALIASES

    expanded = set(permissions)
    for alias, namespace in PERMISSION_ALIASES.items():
        if alias in permissions:
            expanded.add(namespace)
        if namespace in permissions:
            expanded.add(alias)

    return expanded


def userHasPermissions(user, required_permissions, match="all"):
    effective_permissions = getUserPermissionCodenames(user)
    if "*" in effective_permissions:
        return True

    from apps.accounts.permission_catalog import PERMISSION_ALIASES

    required = []
    for perm in required_permissions:
        if not perm:
            continue
        required.append(perm)
        if perm in PERMISSION_ALIASES:
            required.append(PERMISSION_ALIASES[perm])
        else:
            alias = next((key for key, value in PERMISSION_ALIASES.items() if value == perm), None)
            if alias:
                required.append(alias)
    if not required:
        return True

    if match == "any":
        return any(perm in effective_permissions for perm in required)
    return all(perm in effective_permissions for perm in required)


def requirePermissions(request, required_permissions, match="all"):
    user = getattr(request, "user", None)
    if not userHasPermissions(user, required_permissions, match=match):
        raise api_error(
            403,
            ErrorCodes.PERMISSION_DENIED,
            "You do not have permission to perform this action.",
        )
    return True


def permissionRequired(*required_permissions, match="all"):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            requirePermissions(request, required_permissions, match=match)
            return func(request, *args, **kwargs)

        wrapper._required_permissions = required_permissions
        wrapper._permission_match = match
        return wrapper

    return decorator
