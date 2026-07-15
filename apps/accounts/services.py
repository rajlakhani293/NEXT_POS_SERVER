# type: ignore
import secrets
from datetime import timedelta
from typing import Optional

from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.utils import timezone
from django.utils.text import slugify
from apps.accounts.models import AccessToken, PermissionAccess, Role, User, UserAttribute, UserRoleRelation
from apps.accounts.permission_catalog import (
    SOURCE_PERMISSION_CATALOG,
    PERMISSION_ALIASES,
    PERMISSION_CATALOG,
    ROLE_CATALOG,
    ROLE_NAMESPACE_ALIASES,
)
from apps.common.authz import getUserPermissionCodenames
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import serializeModelInstance, validateUniqueFields
from apps.common.tenantDefaults import TenantDefaultsService
from apps.organizations.models import Branch, Company
from apps.settings.services import OptionSettingService


def normalizeRoleNamespace(value):
    namespace = (value or "").strip().lower().replace(" ", "-")
    return ROLE_NAMESPACE_ALIASES.get(namespace, namespace)


class AccountsService:
    PROFILE_ADDRESS_FIELDS = [
        "email",
        "first_name",
        "last_name",
        "phone",
        "address_1",
        "address_2",
        "country",
        "city",
        "pobox",
        "company",
    ]

    @staticmethod
    def buildPermissionDefinitions():
        definitions = []
        seen = set()

        def addDefinition(codename, name):
            if not codename or codename in seen:
                return
            seen.add(codename)
            definitions.append(
                {
                    "codename": codename,
                    "name": name,
                }
            )

        for module, actions in PERMISSION_CATALOG.items():
            for action in actions:
                codename = action if module == "special" else f"{module}_{action}"
                label = action.replace("_", " ").title() if module == "special" else f"{module.replace('_', ' ').title()} {action.replace('_', ' ').title()}"
                addDefinition(codename, label)
        for namespace in SOURCE_PERMISSION_CATALOG:
            label = namespace.replace("pos.", "").replace(".", " ").replace("-", " ").replace("_", " ").title()
            addDefinition(namespace, label)
        for alias, namespace in PERMISSION_ALIASES.items():
            label = alias.replace("_", " ").title()
            addDefinition(alias, label)
        return definitions

    @staticmethod
    def ensurePermissions():
        content_type = ContentType.objects.get_for_model(Role)
        permission_map = {}

        for item in AccountsService.buildPermissionDefinitions():
            permission, _ = Permission.objects.get_or_create(
                content_type=content_type,
                codename=item["codename"],
                defaults={"name": item["name"]},
            )
            if permission.name != item["name"]:
                permission.name = item["name"]
                permission.save(update_fields=["name"])
            permission_map[item["codename"]] = permission

        return permission_map

    @staticmethod
    def seedDefaultRoles(company: Company, branch: Branch):
        permission_map = AccountsService.ensurePermissions()
        all_permissions = list(permission_map.values())
        seeded_roles = []

        for role_blueprint in ROLE_CATALOG:
            role, _created = commonQuery.getOrCreateRecord(
                Role,
                {
                    "company_id": company.id,
                    "branch_id": branch.id,
                    "namespace": role_blueprint["namespace"],
                },
                defaults={
                    "user_id": None,
                    "name": role_blueprint["name"],
                    "description": role_blueprint["description"],
                    "locked": True,
                },
                tenant_config={},
                return_plain=False,
            )
            role.name = role_blueprint["name"]
            role.description = role_blueprint["description"]
            role.locked = True
            role.save(update_fields=["name", "description", "locked"])

            permissions = all_permissions if "*" in role_blueprint["permissions"] else [
                permission_map[codename]
                for codename in role_blueprint["permissions"]
                if codename in permission_map
            ]
            alias_permissions = [
                permission_map[alias]
                for alias, namespace in PERMISSION_ALIASES.items()
                if namespace in role_blueprint["permissions"] and alias in permission_map
            ]
            permissions = list({permission.id: permission for permission in permissions + alias_permissions}.values())
            role.permissions.set(permissions)
            seeded_roles.append(
                {
                    **serializeModelInstance(role),
                    "permissions": [perm.codename for perm in permissions],
                    "flags": role_blueprint.get("flags", {}),
                }
            )

        return seeded_roles

    @staticmethod
    def setUserRoles(user: User, roles):
        role_list = [role for role in roles if role]
        role_ids = [role.id for role in role_list]

        commonQuery.scopedQueryset(UserRoleRelation, {"user_id": user.id}, tenant_config={}).exclude(role_id__in=role_ids).update(
            status=2,
            deleted_at=timezone.now(),
        )
        for role in role_list:
            relation, _created = commonQuery.getOrCreateRecord(
                UserRoleRelation,
                {
                    "user_id": user.id,
                    "role_id": role.id,
                },
                defaults={
                    "company_id": user.company_id,
                    "branch_id": user.branch_id,
                    "status": 0,
                },
                tenant_config={},
                return_plain=False,
            )
            if relation.status != 0:
                relation.status = 0
                relation.deleted_at = None
                relation.save(update_fields=["status", "deleted_at"])

        primary_role = role_list[0] if role_list else None
        user.role = primary_role
        user.save(update_fields=["role"])

    @staticmethod
    def getUserRoles(user: User):
        role_ids = list(
            user.role_relations.filter(status=0).values_list("role_id", flat=True)
        )
        if getattr(user, "role_id", None) and user.role_id not in role_ids:
            role_ids.insert(0, user.role_id)
        return list(
            commonQuery.scopedQueryset(Role, {"id__in": role_ids, "status__in": [0, 1]}, tenant_config={})
            .prefetch_related("permissions")
            .order_by("name")
        )

    @staticmethod
    def serializeUser(user: User):
        user_data = serializeModelInstance(user)
        for key in [
            "password",
            "first_name",
            "last_name",
            "groups",
            "user_permissions",
        ]:
            user_data.pop(key, None)

        roles = AccountsService.getUserRoles(user)
        attribute = AccountsService.serializeUserAttribute(user)
        return {
            **user_data,
            "avatar_link": attribute.get("avatar_link") or user_data.get("profile_image") or "",
            "theme": attribute.get("theme") or "",
            "language": attribute.get("language") or "",
            "attribute": attribute,
            "addresses": AccountsService.serializeProfileAddresses(user),
            "permissions": sorted(list(getUserPermissionCodenames(user))),
            "role": AccountsService.serializeRole(user.role) if getattr(user, "role", None) else None,
            "roles": [AccountsService.serializeRole(role) for role in roles],
        }

    @staticmethod
    def serializeUserAttribute(user: User):
        attribute = UserAttribute.objects.filter(user_id=user.id, status__in=[0, 1]).first()
        if attribute is None:
            return {"avatar_link": "", "theme": "", "language": ""}
        return {
            "avatar_link": attribute.avatar_link or "",
            "theme": attribute.theme or "",
            "language": attribute.language or "",
        }

    @staticmethod
    def upsertUserAttribute(user: User, data):
        fields = {key: data[key] or "" for key in ["avatar_link", "theme", "language"] if key in data}
        if not fields:
            return None
        attribute, _created = UserAttribute.objects.get_or_create(
            user_id=user.id,
            defaults={
                "company_id": user.company_id,
                "branch_id": user.branch_id,
            },
        )
        for field, value in fields.items():
            setattr(attribute, field, value)
        attribute.company_id = user.company_id
        attribute.branch_id = user.branch_id
        attribute.status = 0
        attribute.save()
        return attribute

    @staticmethod
    def serializeProfileAddresses(user: User):
        from apps.customers.models import CustomerAddress

        addresses = {"billing": None, "shipping": None}
        for address in CustomerAddress.objects.filter(customer_id=user.id, status__in=[0, 1]):
            record = serializeModelInstance(address)
            record["company"] = record.get("company_name") or ""
            record.pop("company_name", None)
            addresses[address.type] = record
        return addresses

    @staticmethod
    def upsertProfileAddress(user: User, address_type: str, data):
        if not data:
            return None

        from apps.customers.models import CustomerAddress

        payload = data.dict(exclude_unset=True)
        address_payload = {}
        for field in AccountsService.PROFILE_ADDRESS_FIELDS:
            if field in payload:
                target_field = "company_name" if field == "company" else field
                address_payload[target_field] = payload[field] or ""

        if not address_payload:
            return None

        address, _created = CustomerAddress.objects.get_or_create(
            customer_id=user.id,
            type=address_type,
            defaults={
                "user_id": user.id,
                "company_id": user.company_id,
                "branch_id": user.branch_id,
            },
        )
        for field, value in address_payload.items():
            setattr(address, field, value)
        address.user_id = user.id
        address.company_id = user.company_id
        address.branch_id = user.branch_id
        address.status = 0
        address.save()
        return address


    @staticmethod
    def serializeRole(role: Role):
        return {
            **serializeModelInstance(role),
            "permissions": list(role.permissions.values_list("codename", flat=True)),
        }

    @staticmethod
    def buildSessionData(user: User):
        company = commonQuery.findOneRecord(
            Company,
            {"id": user.company_id, "status__in": [0, 1]},
            tenant_config={},
        )
        branch = commonQuery.findOneRecord(
            Branch,
            {"id": user.branch_id, "company_id": user.company_id, "status__in": [0, 1]},
            tenant_config={},
        )
        branch_list = commonQuery.findAllRecords(
            Branch,
            {"company_id": user.company_id, "status": 0},
            {
                "attributes": ["id", "name", "code", "city", "phone", "is_head_office"],
                "order": ["name"],
            },
            tenant_config={},
        )
        return {
            "user": AccountsService.serializeUser(user),
            "company": company,
            "branch": branch,
            "branch_list": branch_list,
            "business_settings": OptionSettingService.buildSessionSettings(user),
        }

    @staticmethod
    def getDefaultRoleBlueprint():
        return {
            "permissions": AccountsService.buildPermissionDefinitions(),
            "roles": ROLE_CATALOG,
        }

    @staticmethod
    def requestPermissionAccess(user: User, data):
        permission = data.get("permission")
        if not permission:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Permission is required.")
        if permission in getUserPermissionCodenames(user):
            return {"has_permission": True, "access": None}

        now = timezone.now()
        approved = commonQuery.scopedQueryset(
            PermissionAccess,
            {
                "requester": user,
                "company_id": user.company_id,
                "branch_id": user.branch_id,
                "permission": permission,
                "access_status": PermissionAccess.GRANTED,
                "expired_at__gte": now,
                "status": 0,
            },
            tenant_config={},
        ).first()
        if approved:
            return {"has_permission": True, "access": serializeModelInstance(approved)}

        pending = commonQuery.scopedQueryset(
            PermissionAccess,
            {
                "requester": user,
                "company_id": user.company_id,
                "branch_id": user.branch_id,
                "permission": permission,
                "access_status": PermissionAccess.PENDING,
                "expired_at__gte": now,
                "status": 0,
            },
            tenant_config={},
        ).first()
        if pending:
            return {"has_permission": False, "access": serializeModelInstance(pending), "type": "permission_pending"}

        access = commonQuery.createRecord(
            PermissionAccess,
            {
                "requester_id": user.id,
                "granter_id": user.id,
                "company_id": user.company_id,
                "branch_id": user.branch_id,
                "permission": permission,
                "url": data.get("url"),
                "access_status": PermissionAccess.PENDING,
                "expired_at": now + timedelta(minutes=5),
                "status": 0,
            },
            tenant_config={},
        )
        return {"has_permission": False, "access": access, "type": "permission_denied"}

    @staticmethod
    def listPermissionAccess(user: User, data):
        field_config = [["permission", True, True], ["access_status", True, True], ["url", True, False]]
        return commonQuery.fetchPaginatedData(
            PermissionAccess,
            data or {},
            field_config,
            {
                "attributes": [
                    "id",
                    "requester_id",
                    "requester__username",
                    "granter_id",
                    "granter__username",
                    "permission",
                    "url",
                    "access_status",
                    "expired_at",
                    "status",
                    "created_at",
                ],
                "order": ["-created_at"],
            },
            request=None,
            tenant_config={},
            custom_where={"company_id": user.company_id, "branch_id": user.branch_id},
        )

    @staticmethod
    def approvePermissionAccess(user: User, access_id: int, data):
        access = commonQuery.scopedQueryset(
            PermissionAccess,
            {
                "id": access_id,
                "company_id": user.company_id,
                "branch_id": user.branch_id,
                "status": 0,
            },
            tenant_config={},
        ).first()
        if access is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Permission access not found.")
        if access.expired_at and timezone.now() > access.expired_at:
            access.access_status = PermissionAccess.EXPIRED
            access.save(update_fields=["access_status"])
            raise api_error(404, ErrorCodes.NOT_FOUND, "The requested permission access has expired.")
        if access.permission != data.get("permission"):
            raise api_error(403, ErrorCodes.PERMISSION_DENIED, "The requested permission access is not valid.")
        if access.permission not in getUserPermissionCodenames(user):
            raise api_error(403, ErrorCodes.PERMISSION_DENIED, "You do not have access to approve this permission.")
        access.access_status = PermissionAccess.GRANTED
        access.granter = user
        access.save(update_fields=["access_status", "granter", "updated_at"])
        return serializeModelInstance(access)

    @staticmethod
    def markPermissionAccessUsed(user: User, access_id: int):
        access = commonQuery.scopedQueryset(
            PermissionAccess,
            {
                "id": access_id,
                "requester": user,
                "company_id": user.company_id,
                "branch_id": user.branch_id,
                "access_status": PermissionAccess.GRANTED,
                "status": 0,
            },
            tenant_config={},
        ).first()
        if access is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Permission access not found.")
        access.access_status = PermissionAccess.USED
        access.save(update_fields=["access_status", "updated_at"])
        return serializeModelInstance(access)

    @staticmethod
    def generateUniqueCode(model, base_value: str, company_id: Optional[int] = None):
        base_code = slugify(base_value) or "code"
        code = base_code
        counter = 1
        filters = {"code": code}
        if company_id is not None and "company" in [f.name for f in model._meta.get_fields()]:
            filters["company_id"] = company_id

        while commonQuery.existsRecord(model, filters, tenant_config={}):
            counter += 1
            code = f"{base_code}-{counter}"
            filters["code"] = code

        return code

    @staticmethod
    def issueAccessToken(user: User, device_name: str = "", request=None):
        token = commonQuery.createRecord(
            AccessToken,
            {
                "user_id": user.id,
                "token": secrets.token_urlsafe(48),
                "expires_at": timezone.now() + timedelta(days=7),
                "device_name": device_name or "",
                "ip_address": request.META.get("REMOTE_ADDR") if request else None,
                "user_agent": request.META.get("HTTP_USER_AGENT", "") if request else "",
            },
            tenant_config={},
        )
        return {
            "token": token["token"],
            "expires_at": token["expires_at"],
            "user": AccountsService.serializeUser(user),
        }

    @staticmethod
    def register(request, payload):
        if payload.password != payload.password_confirm:
            raise api_error(
                422,
                ErrorCodes.VALIDATION_ERROR,
                "Password confirmation does not match.",
            )
        if commonQuery.existsRecord(User, {"username__iexact": payload.username}, tenant_config={}):
            raise api_error(
                422,
                ErrorCodes.VALIDATION_ERROR,
                "The username is already taken.",
            )
        if payload.email and commonQuery.existsRecord(User, {"email__iexact": payload.email}, tenant_config={}):
            raise api_error(
                422,
                ErrorCodes.VALIDATION_ERROR,
                "The email is already taken.",
            )

        placeholder_company_name = "Enter your company name"
        branch_name = "Main Branch"
        with transaction.atomic():
            company_code = AccountsService.generateUniqueCode(
                Company,
                placeholder_company_name,
            )
            company_data = commonQuery.createRecord(
                Company,
                {
                    "name": placeholder_company_name,
                    "legal_name": placeholder_company_name,
                    "code": company_code,
                    "email": payload.email,
                },
                tenant_config={},
            )
            company = commonQuery.findOneInstance(Company, company_data["id"], tenant_config={})
            branch_data = commonQuery.createRecord(
                Branch,
                {
                    "company_id": company.id,
                    "name": branch_name,
                    "code": AccountsService.generateUniqueCode(
                        Branch,
                        branch_name,
                        company.id,
                    ),
                    "is_head_office": True,
                },
                tenant_config={},
            )
            branch = commonQuery.findOneInstance(Branch, branch_data["id"], tenant_config={})
            TenantDefaultsService.ensureBranchDefaults(company, branch)
            role = commonQuery.scopedQueryset(
                Role,
                {
                    "company": company,
                    "branch": branch,
                    "namespace": "admin",
                    "status": 0,
                },
                tenant_config={},
            ).first()
            if role is None:
                raise api_error(
                    500,
                    ErrorCodes.SERVER_ERROR,
                    "Default administrator role could not be created.",
                )
            user = User.objects.create_user(
                username=payload.username,
                email=payload.email,
                password=payload.password,
                full_name=payload.username,
                company=company,
                branch=branch,
                role=role,
                is_staff=True,
                is_superuser=True,
                status=0,
            )
            AccountsService.setUserRoles(user, [role])

        return AccountsService.issueAccessToken(
            user,
            payload.device_name or "",
            request,
        )

    @staticmethod
    def login(request, payload):
        user = commonQuery.scopedQueryset(User, {"username": payload.username}, tenant_config={}).first()
        if user is None or not user.check_password(payload.password):
            raise api_error(401, ErrorCodes.PERMISSION_DENIED, "Invalid username or password.")
        if user.status != 0 or not user.is_active:
            raise api_error(
                403,
                ErrorCodes.PERMISSION_DENIED,
                "Unable to login, the provided account is not active.",
            )
        return AccountsService.issueAccessToken(
            user,
            payload.device_name or "",
            request,
        )

    @staticmethod
    def passwordLost(payload):
        email = payload.email.strip()
        user = commonQuery.scopedQueryset(
            User,
            {"email__iexact": email, "status__in": [0, 1]},
            tenant_config={},
        ).first()
        if user is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Unable to find a record matching your entry.")

        user.activation_token = secrets.token_urlsafe(15)[:20]
        user.activation_expiration = timezone.now() + timedelta(minutes=30)
        user.save(update_fields=["activation_token", "activation_expiration"])
        return {
            "user_id": user.id,
            "token": user.activation_token,
            "redirectTo": "/sign-in",
        }

    @staticmethod
    def newPassword(user_id: int, token: str, payload):
        if payload.password != payload.password_confirm:
            raise api_error(422, ErrorCodes.VALIDATION_ERROR, "Password confirmation does not match.")

        user = commonQuery.scopedQueryset(
            User,
            {"id": user_id, "status__in": [0, 1]},
            tenant_config={},
        ).first()
        if user is None:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "Unable to find the requested user.")
        if user.status != 0 or not user.is_active:
            raise api_error(403, ErrorCodes.PERMISSION_DENIED, "Unable to submit a new password for a non active user.")
        if user.activation_token != token:
            raise api_error(403, ErrorCodes.PERMISSION_DENIED, "Unable to proceed, the provided token is not valid.")
        if not user.activation_expiration or user.activation_expiration < timezone.now():
            raise api_error(403, ErrorCodes.PERMISSION_DENIED, "Unable to proceed, the token has expired.")

        user.set_password(payload.password)
        user.activation_token = None
        user.activation_expiration = timezone.now()
        user.save(update_fields=["password", "activation_token", "activation_expiration"])
        return {"redirectTo": "/sign-in"}

    @staticmethod
    def activateAccount(user_id: int, token: str):
        user = commonQuery.scopedQueryset(
            User,
            {"id": user_id, "status__in": [0, 1]},
            tenant_config={},
        ).first()
        if user is None:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "Unable to find the requested user.")
        if user.status == 0 and user.is_active:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "No activation is needed for this account.")
        if user.activation_token != token or user.activation_token is None:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid activation token.")
        if not user.activation_expiration or user.activation_expiration < timezone.now():
            raise api_error(400, ErrorCodes.BAD_REQUEST, "The expiration token has expired.")

        user.activation_expiration = None
        user.activation_token = None
        user.status = 0
        user.is_active = True
        user.save(update_fields=["activation_expiration", "activation_token", "status", "is_active"])
        return {"redirectTo": "/sign-in"}

    @staticmethod
    def currentUser(user: User):
        return AccountsService.buildSessionData(user)

    @staticmethod
    def switchBranch(user: User, branch_id: int, request, token_value: str = ""):
        branch = commonQuery.scopedQueryset(
            Branch,
            {
                "id": branch_id,
                "company_id": user.company_id,
                "status": 0,
            },
            tenant_config={},
        ).first()
        if branch is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")

        user.branch = branch
        user.save(update_fields=["branch"])

        if token_value:
            commonQuery.scopedQueryset(AccessToken, {"token": token_value}, tenant_config={}).update(
                status=1,
                deleted_at=timezone.now(),
            )

        token_data = AccountsService.issueAccessToken(user, "Branch Switch", request)
        return {
            "token": token_data["token"],
            "expires_at": token_data["expires_at"],
            "session": AccountsService.buildSessionData(user),
        }

    @staticmethod
    def logout(token_value: str):
        commonQuery.scopedQueryset(AccessToken, {"token": token_value}, tenant_config={}).update(
            status=2,
            deleted_at=timezone.now(),
        )
        return {"logged_out": True}

    @staticmethod
    def listAccessTokens(user: User):
        return [
            {
                **serializeModelInstance(token),
                "name": token.device_name or "",
                "token": token.token[-8:].rjust(len(token.token), "*"),
                "expired": token.is_expired,
            }
            for token in AccessToken.objects.filter(user=user, status=0).order_by("-created_at")
        ]

    @staticmethod
    def createAccessToken(user: User, request, data):
        return AccountsService.issueAccessToken(user, data.get("device_name") or data.get("name") or "", request)

    @staticmethod
    def deleteAccessToken(user: User, token_id: int):
        count = AccessToken.objects.filter(user=user, id=token_id, status=0).update(
            status=2,
            deleted_at=timezone.now(),
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Access token not found.")
        return {"deleted_count": count}

    @staticmethod
    def checkPermission(user: User, data):
        permission = data.get("permission") or data.get("namespace") or data.get("codename")
        if not permission:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Permission is required.")
        return {
            "permission": permission,
            "allowed": permission in getUserPermissionCodenames(user),
        }

    @staticmethod
    def _modelHasField(model, field_name: str):
        return any(field.name == field_name for field in model._meta.get_fields())

    @staticmethod
    def _deleteQueryset(label: str, queryset, deleted_summary: dict):
        count = queryset.count()
        if count == 0:
            return 0
        deleted_count, deleted_map = queryset.delete()
        deleted_summary[label] = deleted_summary.get(label, 0) + count
        for model_label, model_count in deleted_map.items():
            deleted_summary[model_label] = deleted_summary.get(model_label, 0) + model_count
        return deleted_count

    @staticmethod
    def _deleteCompanyScopedModels(company_id: int):
        deleted_summary = {}
        blocked_labels = {}

        ordered_labels = [
            "sales.OrdersProductsRefund",
            "sales.OrdersRefund",
            "sales.OrderPayment",
            "promotions.OrdersCoupon",
            "sales.OrderInstalment",
            "sales.OrdersProduct",
            "sales.Order",
            "purchases.ProcurementsProduct",
            "purchases.Procurement",
            "registers.RegistersHistory",
            "catalog.ProductTax",
            "catalog.ProductHistory",
            "catalog.ProductHistoryCombined",
            "catalog.ProductSubItem",
            "catalog.ProductMeta",
            "catalog.ProductUnitQuantity",
            "catalog.ProductGallery",
            "customers.CustomerCoupon",
            "customers.CustomerReward",
            "rewards.RewardSystemRule",
            "rewards.RewardSystem",
            "promotions.CouponProduct",
            "promotions.CouponCategory",
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
            "catalog.ScaleRange",
            "accounting.TransactionHistory",
            "accounting.Transaction",
            "accounting.TransactionBalanceDay",
            "accounting.TransactionBalanceMonth",
            "accounting.TransactionAccount",
            "settings.PaymentType",
            "registers.Register",
            "settings.Option",
            "reports.DashboardDay",
            "reports.DashboardWeek",
            "reports.DashboardMonth",
            "settings.Notification",
            "settings.Media",
            "accounts.PermissionAccess",
            "accounts.Role",
            "organizations.Branch",
        ]

        def delete_model(model):
            if not AccountsService._modelHasField(model, "company"):
                return 0
            queryset = commonQuery.scopedQueryset(model, {"company_id": company_id}, tenant_config={})
            return AccountsService._deleteQueryset(model._meta.label, queryset, deleted_summary)

        for label in ordered_labels:
            try:
                model = apps.get_model(label)
            except LookupError:
                continue
            try:
                delete_model(model)
                blocked_labels.pop(model._meta.label, None)
            except (ProtectedError, RestrictedError) as err:
                blocked_labels[model._meta.label] = str(err)

        company_scoped_models = [
            model
            for model in apps.get_models()
            if model._meta.label not in ["organizations.Company", "accounts.User"]
            and AccountsService._modelHasField(model, "company")
        ]

        for _attempt in range(8):
            deleted_any = False
            for model in company_scoped_models:
                try:
                    deleted_count = delete_model(model)
                    if deleted_count:
                        deleted_any = True
                    blocked_labels.pop(model._meta.label, None)
                except (ProtectedError, RestrictedError) as err:
                    blocked_labels[model._meta.label] = str(err)
            if not deleted_any:
                break

        remaining = {}
        for model in company_scoped_models:
            count = commonQuery.countRecords(model, {"company_id": company_id}, tenant_config={})
            if count:
                remaining[model._meta.label] = count

        if remaining:
            raise api_error(
                500,
                ErrorCodes.SERVER_ERROR,
                "Workspace cleanup could not delete all company related records.",
                data={"remaining": remaining, "blocked": blocked_labels},
            )

        return deleted_summary

    @staticmethod
    def deleteWorkspace(user: User):
        if user is None or not user.company_id:
            raise api_error(
                400,
                ErrorCodes.WORKSPACE_NOT_FOUND,
                "No workspace is linked to this account.",
            )

        if not user.is_superuser:
            raise api_error(
                403,
                ErrorCodes.PERMISSION_DENIED,
                "Only the workspace super admin can delete this workspace.",
            )

        company = commonQuery.findOneInstance(Company, user.company_id, tenant_config={})
        if company is None:
            raise api_error(
                404,
                ErrorCodes.COMPANY_NOT_FOUND,
                "Workspace company was not found.",
            )

        user_ids = list(
            commonQuery.scopedQueryset(User, {"company_id": company.id}, tenant_config={}).values_list("id", flat=True)
        )
        branch_ids = list(
            commonQuery.scopedQueryset(Branch, {"company_id": company.id}, tenant_config={}).values_list("id", flat=True)
        )
        role_ids = list(
            commonQuery.scopedQueryset(Role, {"company_id": company.id}, tenant_config={}).values_list("id", flat=True)
        )

        with transaction.atomic():
            token_count, _ = commonQuery.scopedQueryset(AccessToken, {"user_id__in": user_ids}, tenant_config={}).delete()
            tenant_deleted_summary = AccountsService._deleteCompanyScopedModels(company.id)
            deleted_user_count, _ = commonQuery.scopedQueryset(User, {"id__in": user_ids}, tenant_config={}).delete()
            deleted_company_count, _ = commonQuery.scopedQueryset(Company, {"id": company.id}, tenant_config={}).delete()

        return {
            "company_id": company.id,
            "branch_ids": branch_ids,
            "role_ids": role_ids,
            "user_ids": user_ids,
            "deleted_access_token_count": token_count,
            "deleted_tenant_records": tenant_deleted_summary,
            "deleted_company_count": deleted_company_count,
            "deleted_user_count": deleted_user_count,
            "note": "Shared Django permission definitions are global and were not deleted.",
        }

    @staticmethod
    def listUsers(user: User, data):
        field_config = [["username", True, True], ["full_name", True, False]]
        result = commonQuery.fetchPaginatedData(
            User,
            data,
            field_config,
            {
                "attributes": [
                    "id",
                    "username",
                    "full_name",
                    "email",
                    "account_amount",
                    "owed_amount",
                    "purchases_amount",
                    "status",
                    "date_joined",
                ]
            },
            tenant_config={},
            custom_where={"company_id": user.company_id},
        )

        # Batch-fetch roles for each user in page.
        user_ids = [item["id"] for item in result["items"]]
        relations = (
            UserRoleRelation.objects.filter(user_id__in=user_ids, status=0)
            .select_related("role")
        )
        roles_map: dict = {}
        for rel in relations:
            roles_map.setdefault(rel.user_id, []).append(rel.role.name)
        for item in result["items"]:
            names = roles_map.get(item["id"], [])
            item["roles_names"] = ", ".join(names) if names else "Not Assigned"
            item["created_at"] = item.pop("date_joined", None)

        return result

    @staticmethod
    def userDropdown(user: User):
        return commonQuery.findAllRecords(
            User,
            {"company_id": user.company_id, "status__in": [0, 1]},
            {
                "attributes": ["id", "full_name", "phone", "email"],
                "order": ["full_name"],
            },
            tenant_config={},
        )

    @staticmethod
    def getUser(user: User, user_id: int):
        target_user = (
            commonQuery.scopedQueryset(
                User,
                {"company_id": user.company_id, "id": user_id, "status__in": [0, 1]},
                tenant_config={},
            )
            .select_related("branch", "role")
            .first()
        )
        if target_user is None:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "User not found.")
        return AccountsService.serializeUser(target_user)

    @staticmethod
    def createUser(user: User, payload):
        data = payload.dict(exclude_unset=True)
        branch_id = data.get("branch_id") or user.branch_id
        role_id = data.get("role_id")
        role_ids = data.get("roles") or ([role_id] if role_id else [])

        branch = commonQuery.scopedQueryset(
            Branch,
            {"company_id": user.company_id, "id": branch_id, "status__in": [0, 1]},
            tenant_config={},
        ).first()
        if branch is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")

        roles = []
        if role_ids:
            roles = list(commonQuery.scopedQueryset(
                Role,
                {"company_id": user.company_id, "branch_id": branch_id, "id__in": role_ids, "status__in": [0, 1]},
                tenant_config={},
            ))
            if len(roles) != len(set(role_ids)):
                raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")
        role = roles[0] if roles else None

        username = data.get("username")
        password = data.get("password")
        full_name = data.get("full_name") or username
        phone = data.get("phone") or ""
        email = data.get("email") or ""
        validateUniqueFields(
            User,
            {"username": username, "phone": phone, "email": email},
            scope="global",
            status_in=(0, 1),
            case_insensitive=["username", "email"],
            messages={
                "username": "Username already exists.",
                "phone": "Phone already exists.",
                "email": "Email already exists.",
            },
        )

        target_user = User.objects.create_user(
            username=username,
            password=password,
            company_id=user.company_id,
            branch=branch,
            role=role,
            full_name=data.get("full_name") or full_name,
            first_name=data.get("first_name") or "",
            last_name=data.get("last_name") or "",
            phone=phone,
            email=email,
            gender=data.get("gender") or "",
            pobox=data.get("pobox") or "",
            birth_date=data.get("birth_date"),
            credit_limit_amount=data.get("credit_limit_amount") or 0,
            status=0 if data.get("active", True) else 1,
            is_active=bool(data.get("active", True)),
        )
        if roles:
            AccountsService.setUserRoles(target_user, roles)
        return AccountsService.serializeUser(target_user)

    @staticmethod
    def updateUser(user: User, user_id: int, payload):
        target_user = commonQuery.scopedQueryset(
            User,
            {"company_id": user.company_id, "id": user_id, "status__in": [0, 1]},
            tenant_config={},
        ).first()
        if target_user is None:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "User not found.")

        data = payload.dict(exclude_unset=True)
        validateUniqueFields(
            User,
            {
                "username": data.get("username"),
                "phone": data.get("phone"),
                "email": data.get("email"),
            },
            scope="global",
            exclude_id=user_id,
            status_in=(0, 1),
            case_insensitive=["username", "email"],
            messages={
                "username": "Username already exists.",
                "phone": "Phone already exists.",
                "email": "Email already exists.",
            },
        )
        if data.get("branch_id"):
            branch = commonQuery.scopedQueryset(
                Branch,
                {"company_id": user.company_id, "id": data["branch_id"], "status__in": [0, 1]},
                tenant_config={},
            ).first()
            if branch is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")
            target_user.branch = branch
        role_ids = data.get("roles")
        if role_ids is None and data.get("role_id"):
            role_ids = [data["role_id"]]
        if role_ids is not None:
            role_ids = [role_id for role_id in role_ids if role_id]
            roles = list(commonQuery.scopedQueryset(
                Role,
                {
                    "company_id": user.company_id,
                    "branch_id": target_user.branch_id,
                    "id__in": role_ids,
                    "status__in": [0, 1],
                },
                tenant_config={},
            ))
            if len(roles) != len(set(role_ids)):
                raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")
            AccountsService.setUserRoles(target_user, roles)

        for field in ["username", "full_name", "first_name", "last_name", "phone", "email", "gender", "pobox"]:
            if field in data:
                setattr(target_user, field, data[field] or "")
        if "birth_date" in data:
            target_user.birth_date = data["birth_date"]
        if "credit_limit_amount" in data and data["credit_limit_amount"] is not None:
            target_user.credit_limit_amount = data["credit_limit_amount"]
        if "active" in data and data["active"] is not None:
            target_user.status = 0 if data["active"] else 1
            target_user.is_active = bool(data["active"])
        if "status" in data and data["status"] is not None:
            target_user.status = data["status"]
        if data.get("group_id"):
            from apps.customers.models import CustomerGroup
            group = commonQuery.scopedQueryset(
                CustomerGroup,
                {"company_id": user.company_id, "id": data["group_id"]},
                tenant_config={},
            ).first()
            target_user.group = group
        if data.get("password"):
            target_user.set_password(data["password"])
        target_user.save()
        return AccountsService.serializeUser(target_user)

    @staticmethod
    def updateOwnProfile(user: User, payload):
        data = payload.dict(exclude_unset=True)

        validateUniqueFields(
            User,
            {
                "username": data.get("username"),
                "phone": data.get("phone"),
                "email": data.get("email"),
            },
            scope="global",
            exclude_id=user.id,
            status_in=(0, 1),
            case_insensitive=["username", "email"],
            messages={
                "username": "Username already exists.",
                "phone": "Phone already exists.",
                "email": "Email already exists.",
            },
        )

        for field in ["username", "full_name", "phone", "email"]:
            if field in data:
                setattr(user, field, data[field] or "")

        if "avatar_link" in data:
            user.profile_image = data["avatar_link"] or ""
        AccountsService.upsertUserAttribute(user, data)

        for address_type in ["billing", "shipping"]:
            AccountsService.upsertProfileAddress(user, address_type, getattr(payload, address_type, None))

        password = data.get("password") or ""
        if password:
            if password != (data.get("password_confirm") or ""):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Password confirmation does not match.")
            if not user.check_password(data.get("old_password") or ""):
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Wrong old password provided")
            user.set_password(password)

        user.save()
        return AccountsService.serializeUser(user)

    @staticmethod
    def deleteUsers(user: User, data):
        ids = data.get("ids", [])
        if not isinstance(ids, list):
            ids = [ids]
        if user.id in ids:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "You cannot delete your own account.")
        count = commonQuery.scopedQueryset(
            User,
            {"company_id": user.company_id, "id__in": ids},
            tenant_config={},
        ).update(status=2, deleted_at=timezone.now())
        if count == 0:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "User not found.")
        return {"deleted_count": count}

    @staticmethod
    def updateUserStatus(user: User, data):
        status = data.get("status")
        ids = data.get("ids", [])
        if not isinstance(ids, list):
            ids = [ids]
        if user.id in ids and status in [1, 2]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "You cannot disable your own account.")
        count = commonQuery.scopedQueryset(
            User,
            {"company_id": user.company_id, "id__in": ids},
            tenant_config={},
        ).update(status=status)
        if count == 0:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "User not found.")
        return {"updated_count": count, "status": status}

    @staticmethod
    def listRoles(user: User):
        AccountsService.ensurePermissions()
        roles = (
            commonQuery.scopedQueryset(
                Role,
                {"company_id": user.company_id, "branch_id": user.branch_id, "status__in": [0, 1]},
                tenant_config={},
            )
            .prefetch_related("permissions")
            .order_by("name")
        )
        return [AccountsService.serializeRole(role) for role in roles]

    @staticmethod
    def getRole(user: User, role_id: int):
        AccountsService.ensurePermissions()
        role = (
            commonQuery.scopedQueryset(
                Role,
                {"company_id": user.company_id, "branch_id": user.branch_id, "id": role_id, "status__in": [0, 1]},
                tenant_config={},
            )
            .prefetch_related("permissions")
            .first()
        )
        if role is None:
            raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")
        return AccountsService.serializeRole(role)

    @staticmethod
    def createRole(user: User, payload):
        permission_map = AccountsService.ensurePermissions()
        requested_permissions = payload.permission_codenames or []
        invalid_permissions = [code for code in requested_permissions if code not in permission_map]
        if invalid_permissions:
            raise api_error(
                400,
                ErrorCodes.INVALID_PERMISSIONS,
                f"Invalid permissions: {', '.join(invalid_permissions)}",
            )

        role_namespace = normalizeRoleNamespace(payload.namespace or slugify(payload.name))
        validateUniqueFields(
            Role,
            {"namespace": role_namespace},
            scope=None,
            status_in=(0, 1),
            extra_filters={"company_id": user.company_id, "branch_id": user.branch_id},
            messages={"namespace": "Role namespace already exists."},
        )
        validateUniqueFields(
            Role,
            {"name": payload.name},
            scope=None,
            status_in=(0, 1),
            extra_filters={"company_id": user.company_id, "branch_id": user.branch_id},
            messages={"name": "Role name already exists."},
        )

        role_data = commonQuery.createRecord(
            Role,
            {
                "company_id": user.company_id,
                "branch_id": user.branch_id,
                "user_id": user.id,
                "name": payload.name,
                "namespace": role_namespace,
                "description": payload.description,
                "reward_system_id": payload.reward_system_id,
                "minimal_credit_payment": payload.minimal_credit_payment,
                "locked": False,
            },
            tenant_config={},
        )
        role = commonQuery.findOneInstance(Role, role_data["id"], tenant_config={})
        role.permissions.set([permission_map[code] for code in requested_permissions])
        return AccountsService.serializeRole(role)

    @staticmethod
    def updateRole(user: User, role_id: int, payload):
        role = (
            commonQuery.scopedQueryset(
                Role,
                {"company_id": user.company_id, "branch_id": user.branch_id, "id": role_id, "status__in": [0, 1]},
                tenant_config={},
            )
            .prefetch_related("permissions")
            .first()
        )
        if role is None:
            raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")

        data = payload.dict(exclude_unset=True)
        permission_codenames = data.pop("permission_codenames", None)
        if role.locked:
            data.pop("namespace", None)
            data.pop("locked", None)

        if "namespace" in data and data["namespace"]:
            data["namespace"] = normalizeRoleNamespace(data["namespace"])
            validateUniqueFields(
                Role,
                {"namespace": data["namespace"]},
                scope=None,
                exclude_id=role_id,
                status_in=(0, 1),
                extra_filters={"company_id": user.company_id, "branch_id": user.branch_id},
                messages={"namespace": "Role namespace already exists."},
            )
        if "name" in data and data["name"]:
            validateUniqueFields(
                Role,
                {"name": data["name"]},
                scope=None,
                exclude_id=role_id,
                status_in=(0, 1),
                extra_filters={"company_id": user.company_id, "branch_id": user.branch_id},
                messages={"name": "Role name already exists."},
            )

        for field, value in data.items():
            setattr(role, field, value)
        role.save()

        if permission_codenames is not None:
            permission_map = AccountsService.ensurePermissions()
            invalid_permissions = [code for code in permission_codenames if code not in permission_map]
            if invalid_permissions:
                raise api_error(
                    400,
                    ErrorCodes.INVALID_PERMISSIONS,
                    f"Invalid permissions: {', '.join(invalid_permissions)}",
                )
            role.permissions.set([permission_map[code] for code in permission_codenames])

        return AccountsService.serializeRole(role)

    @staticmethod
    def updateRolesPermissions(user: User, payload: dict):
        permission_map = AccountsService.ensurePermissions()
        roles = commonQuery.scopedQueryset(
            Role,
            {"company_id": user.company_id, "branch_id": user.branch_id, "status__in": [0, 1]},
            tenant_config={},
        ).prefetch_related("permissions")
        roles_by_namespace = {role.namespace: role for role in roles}

        for role_namespace, permissions in (payload or {}).items():
            role = roles_by_namespace.get(role_namespace)
            if role is None:
                continue
            if isinstance(permissions, dict):
                granted = [codename for codename, enabled in permissions.items() if enabled]
            else:
                granted = list(permissions or [])
            invalid_permissions = [code for code in granted if code not in permission_map]
            if invalid_permissions:
                raise api_error(
                    400,
                    ErrorCodes.INVALID_PERMISSIONS,
                    f"Invalid permissions: {', '.join(invalid_permissions)}",
                )
            role.permissions.set([permission_map[code] for code in granted])

        return {"updated": True}

    @staticmethod
    def deleteRole(user: User, role_id: int):
        role = commonQuery.scopedQueryset(
            Role,
            {"company_id": user.company_id, "branch_id": user.branch_id, "id": role_id, "status__in": [0, 1]},
            tenant_config={},
        ).first()
        if role is None:
            raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")
        if role.locked or role.namespace == "admin":
            raise api_error(
                400,
                ErrorCodes.ADMINISTRATOR_ROLE_DELETE_FORBIDDEN,
                "Locked role cannot be deleted.",
            )
        if role.users.filter(status__in=[0, 1]).exists() or role.user_relations.filter(status=0, user__status__in=[0, 1]).exists():
            raise api_error(
                400,
                ErrorCodes.ROLE_IN_USE,
                "This role is assigned to active users and cannot be deleted.",
            )

        deleted = commonQuery.softDeleteById(
            Role,
            {"id": role_id, "company_id": user.company_id, "branch_id": user.branch_id},
            tenant_config={},
        )
        if not deleted:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Role could not be deleted.")
        return {"deleted": True}

    @staticmethod
    def assignRole(user: User, user_id: int, role_id: int):
        target_user = commonQuery.scopedQueryset(
            User,
            {"company_id": user.company_id, "id": user_id, "status__in": [0, 1]},
            tenant_config={},
        ).first()
        if target_user is None:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "User not found.")

        role = commonQuery.scopedQueryset(
            Role,
            {"company_id": user.company_id, "branch_id": user.branch_id, "id": role_id, "status__in": [0, 1]},
            tenant_config={},
        ).first()
        if role is None:
            raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")

        AccountsService.setUserRoles(target_user, [role])
        return AccountsService.serializeUser(target_user)
