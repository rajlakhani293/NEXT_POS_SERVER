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
from apps.accounts.models import AccessToken, PermissionAccess, Role, User, UserRoleRelation
from apps.accounts.permission_catalog import PERMISSION_CATALOG, ROLE_CATALOG
from apps.common.authz import get_user_permission_codenames
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import serializeModelInstance, validateUniqueFields
from apps.common.tenantDefaults import TenantDefaultsService
from apps.organizations.models import Branch, Company
from apps.settings.services import OptionSettingService


def normalizeRoleNamespace(value):
    return (value or "").strip().lower().replace(" ", "-")


class AccountsService:
    @staticmethod
    def buildPermissionDefinitions():
        definitions = []
        for module, actions in PERMISSION_CATALOG.items():
            for action in actions:
                codename = action if module == "special" else f"{module}_{action}"
                label = action.replace("_", " ").title() if module == "special" else f"{module.replace('_', ' ').title()} {action.replace('_', ' ').title()}"
                definitions.append(
                    {
                        "codename": codename,
                        "name": label,
                    }
                )
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
            role, _created = Role.objects.get_or_create(
                company_id=company.id,
                branch_id=branch.id,
                namespace=role_blueprint["namespace"],
                defaults={
                    "user_id": None,
                    "name": role_blueprint["name"],
                    "description": role_blueprint["description"],
                    "locked": True,
                },
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

        UserRoleRelation.objects.filter(user_id=user.id).exclude(role_id__in=role_ids).update(
            status=2,
            deleted_at=timezone.now(),
        )
        for role in role_list:
            relation, _created = UserRoleRelation.objects.get_or_create(
                user_id=user.id,
                role_id=role.id,
                defaults={
                    "company_id": user.company_id,
                    "branch_id": user.branch_id,
                    "status": 0,
                },
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
            Role.objects.filter(id__in=role_ids, status__in=[0, 1])
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
        return {
            **user_data,
            "permissions": sorted(list(get_user_permission_codenames(user))),
            "role": AccountsService.serializeRole(user.role) if getattr(user, "role", None) else None,
            "roles": [AccountsService.serializeRole(role) for role in roles],
        }

    @staticmethod
    def serializeRole(role: Role):
        return {
            **serializeModelInstance(role),
            "permissions": list(role.permissions.values_list("codename", flat=True)),
        }

    @staticmethod
    def buildSessionData(user: User):
        company = Company.objects.filter(id=user.company_id, status__in=[0, 1]).first()
        branch = Branch.objects.filter(id=user.branch_id, company_id=user.company_id, status__in=[0, 1]).first()
        branch_list = list(
            Branch.objects.filter(company_id=user.company_id, status=0)
            .order_by("name")
            .values("id", "name", "code", "city", "phone", "is_head_office")
        )
        return {
            "user": AccountsService.serializeUser(user),
            "company": serializeModelInstance(company),
            "branch": serializeModelInstance(branch),
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
        if permission in get_user_permission_codenames(user):
            return {"has_permission": True, "access": None}

        now = timezone.now()
        approved = PermissionAccess.objects.filter(
            requester=user,
            company_id=user.company_id,
            branch_id=user.branch_id,
            permission=permission,
            access_status=PermissionAccess.GRANTED,
            expired_at__gte=now,
            status=0,
        ).first()
        if approved:
            return {"has_permission": True, "access": serializeModelInstance(approved)}

        pending = PermissionAccess.objects.filter(
            requester=user,
            company_id=user.company_id,
            branch_id=user.branch_id,
            permission=permission,
            access_status=PermissionAccess.PENDING,
            expired_at__gte=now,
            status=0,
        ).first()
        if pending:
            return {"has_permission": False, "access": serializeModelInstance(pending), "type": "permission_pending"}

        access = PermissionAccess.objects.create(
            requester=user,
            granter=user,
            company_id=user.company_id,
            branch_id=user.branch_id,
            permission=permission,
            url=data.get("url"),
            access_status=PermissionAccess.PENDING,
            expired_at=now + timedelta(minutes=5),
            status=0,
        )
        return {"has_permission": False, "access": serializeModelInstance(access), "type": "permission_denied"}

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
        access = PermissionAccess.objects.filter(
            id=access_id,
            company_id=user.company_id,
            branch_id=user.branch_id,
            status=0,
        ).first()
        if access is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Permission access not found.")
        if access.expired_at and timezone.now() > access.expired_at:
            access.access_status = PermissionAccess.EXPIRED
            access.save(update_fields=["access_status"])
            raise api_error(404, ErrorCodes.NOT_FOUND, "The requested permission access has expired.")
        if access.permission != data.get("permission"):
            raise api_error(403, ErrorCodes.PERMISSION_DENIED, "The requested permission access is not valid.")
        if access.permission not in get_user_permission_codenames(user):
            raise api_error(403, ErrorCodes.PERMISSION_DENIED, "You do not have access to approve this permission.")
        access.access_status = PermissionAccess.GRANTED
        access.granter = user
        access.save(update_fields=["access_status", "granter", "updated_at"])
        return serializeModelInstance(access)

    @staticmethod
    def markPermissionAccessUsed(user: User, access_id: int):
        access = PermissionAccess.objects.filter(
            id=access_id,
            requester=user,
            company_id=user.company_id,
            branch_id=user.branch_id,
            access_status=PermissionAccess.GRANTED,
            status=0,
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

        while model.objects.filter(**filters).exists():
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
        if User.objects.filter(username__iexact=payload.username).exists():
            raise api_error(
                422,
                ErrorCodes.VALIDATION_ERROR,
                "The username is already taken.",
            )
        if payload.email and User.objects.filter(email__iexact=payload.email).exists():
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
            company = Company.objects.create(
                name=placeholder_company_name,
                legal_name=placeholder_company_name,
                code=company_code,
                email=payload.email,
            )
            branch = Branch.objects.create(
                company=company,
                name=branch_name,
                code=AccountsService.generateUniqueCode(
                    Branch,
                    branch_name,
                    company.id,
                ),
                is_head_office=True,
            )
            TenantDefaultsService.ensureBranchDefaults(company, branch)
            role = Role.objects.filter(
                company=company,
                branch=branch,
                namespace="admin",
                status=0,
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
        user = User.objects.filter(username=payload.username).first()
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
    def currentUser(user: User):
        return AccountsService.buildSessionData(user)

    @staticmethod
    def switchBranch(user: User, branch_id: int, request, token_value: str = ""):
        branch = Branch.objects.filter(
            id=branch_id,
            company_id=user.company_id,
            status=0,
        ).first()
        if branch is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")

        user.branch = branch
        user.save(update_fields=["branch"])

        if token_value:
            AccessToken.objects.filter(token=token_value).update(
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
        AccessToken.objects.filter(token=token_value).update(
            status=2,
            deleted_at=timezone.now(),
        )
        return {"logged_out": True}

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
            "rewards.RewardsSystemRule",
            "rewards.RewardSystem",
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
            queryset = model.objects.filter(company_id=company_id)
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
            count = model.objects.filter(company_id=company_id).count()
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

        company = Company.objects.filter(id=user.company_id).first()
        if company is None:
            raise api_error(
                404,
                ErrorCodes.COMPANY_NOT_FOUND,
                "Workspace company was not found.",
            )

        user_ids = list(
            User.objects.filter(company_id=company.id).values_list("id", flat=True)
        )
        branch_ids = list(
            Branch.objects.filter(company_id=company.id).values_list("id", flat=True)
        )
        role_ids = list(
            Role.objects.filter(company_id=company.id).values_list("id", flat=True)
        )

        with transaction.atomic():
            token_count, _ = AccessToken.objects.filter(user_id__in=user_ids).delete()
            tenant_deleted_summary = AccountsService._deleteCompanyScopedModels(company.id)
            deleted_user_count, _ = User.objects.filter(id__in=user_ids).delete()
            deleted_company_count, _ = Company.objects.filter(id=company.id).delete()

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
        field_config = [["full_name", True, True], ["phone", True, False], ["email", True, False]]
        return commonQuery.fetchPaginatedData(
            User,
            data,
            field_config,
            {
                "attributes": [
                    "id",
                    "username",
                    "full_name",
                    "phone",
                    "email",
                    "branch_id",
                    "branch__name",
                    "role_id",
                    "role__name",
                    "status",
                ]
            },
            tenant_config={},
            custom_where={"company_id": user.company_id},
        )

    @staticmethod
    def userDropdown(user: User):
        return list(
            User.objects.filter(company_id=user.company_id, status__in=[0, 1])
            .order_by("full_name")
            .values("id", "full_name", "phone", "email")
        )

    @staticmethod
    def getUser(user: User, user_id: int):
        target_user = (
            User.objects.filter(company_id=user.company_id, id=user_id, status__in=[0, 1])
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

        branch = Branch.objects.filter(company_id=user.company_id, id=branch_id, status__in=[0, 1]).first()
        if branch is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")

        role = None
        if role_id:
            role = Role.objects.filter(company_id=user.company_id, branch_id=branch_id, id=role_id, status__in=[0, 1]).first()
            if role is None:
                raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")

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
            full_name=full_name,
            phone=phone,
            email=email,
            status=data.get("status", 0),
        )
        if role:
            AccountsService.setUserRoles(target_user, [role])
        return AccountsService.serializeUser(target_user)

    @staticmethod
    def updateUser(user: User, user_id: int, payload):
        target_user = User.objects.filter(company_id=user.company_id, id=user_id, status__in=[0, 1]).first()
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
            branch = Branch.objects.filter(company_id=user.company_id, id=data["branch_id"], status__in=[0, 1]).first()
            if branch is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")
            target_user.branch = branch
        if data.get("role_id"):
            role = Role.objects.filter(
                company_id=user.company_id,
                branch_id=target_user.branch_id,
                id=data["role_id"],
                status__in=[0, 1],
            ).first()
            if role is None:
                raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")
            AccountsService.setUserRoles(target_user, [role])

        for field in ["username", "full_name", "phone", "email"]:
            if field in data:
                setattr(target_user, field, data[field] or "")
        if data.get("password"):
            target_user.set_password(data["password"])
        if "status" in data:
            target_user.status = data["status"]
        target_user.save()
        return AccountsService.serializeUser(target_user)

    @staticmethod
    def deleteUsers(user: User, data):
        ids = data.get("ids", [])
        if not isinstance(ids, list):
            ids = [ids]
        count = User.objects.filter(company_id=user.company_id, id__in=ids).update(status=2, deleted_at=timezone.now())
        if count == 0:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "User not found.")
        return {"deleted_count": count}

    @staticmethod
    def updateUserStatus(user: User, data):
        status = data.get("status")
        ids = data.get("ids", [])
        if not isinstance(ids, list):
            ids = [ids]
        count = User.objects.filter(company_id=user.company_id, id__in=ids).update(status=status)
        if count == 0:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "User not found.")
        return {"updated_count": count, "status": status}

    @staticmethod
    def listRoles(user: User):
        AccountsService.ensurePermissions()
        roles = (
            Role.objects.filter(company_id=user.company_id, branch_id=user.branch_id, status__in=[0, 1])
            .prefetch_related("permissions")
            .order_by("name")
        )
        return [AccountsService.serializeRole(role) for role in roles]

    @staticmethod
    def getRole(user: User, role_id: int):
        AccountsService.ensurePermissions()
        role = (
            Role.objects.filter(company_id=user.company_id, branch_id=user.branch_id, id=role_id, status__in=[0, 1])
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

        role = Role.objects.create(
            company_id=user.company_id,
            branch_id=user.branch_id,
            user_id=user.id,
            name=payload.name,
            namespace=role_namespace,
            description=payload.description,
            reward_system_id=payload.reward_system_id,
            minimal_credit_payment=payload.minimal_credit_payment,
            locked=payload.locked,
        )
        role.permissions.set([permission_map[code] for code in requested_permissions])
        return AccountsService.serializeRole(role)

    @staticmethod
    def updateRole(user: User, role_id: int, payload):
        role = (
            Role.objects.filter(company_id=user.company_id, branch_id=user.branch_id, id=role_id, status__in=[0, 1])
            .prefetch_related("permissions")
            .first()
        )
        if role is None:
            raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")

        data = payload.dict(exclude_unset=True)
        permission_codenames = data.pop("permission_codenames", None)

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
    def deleteRole(user: User, role_id: int):
        role = Role.objects.filter(company_id=user.company_id, branch_id=user.branch_id, id=role_id, status__in=[0, 1]).first()
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
        target_user = User.objects.filter(company_id=user.company_id, id=user_id, status__in=[0, 1]).first()
        if target_user is None:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "User not found.")

        role = Role.objects.filter(company_id=user.company_id, branch_id=user.branch_id, id=role_id, status__in=[0, 1]).first()
        if role is None:
            raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")

        AccountsService.setUserRoles(target_user, [role])
        return AccountsService.serializeUser(target_user)
