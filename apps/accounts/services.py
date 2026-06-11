# type: ignore
import secrets
import random
import os
from datetime import timedelta
from typing import Optional

from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.utils import timezone
from django.utils.text import slugify
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from apps.accounts.models import AccessToken, OtpRequest, Role, User
from apps.accounts.permission_catalog import PERMISSION_CATALOG, ROLE_CATALOG
from apps.common.authz import get_user_permission_codenames
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import serializeModelInstance, validateUniqueFields
from apps.expenses.services import ExpenseCategoryService
from apps.organizations.models import Branch, Company
from apps.payments.services import PaymentTypeService
from apps.registers.services import RegisterService
from apps.settingsapi.services import BusinessSettingService


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
    def seedDefaultRoles(company: Company):
        permission_map = AccountsService.ensurePermissions()
        all_permissions = list(permission_map.values())
        seeded_roles = []

        for role_blueprint in ROLE_CATALOG:
            role, _created = Role.objects.get_or_create(
                company_id=company.id,
                code=role_blueprint["code"],
                defaults={
                    "name": role_blueprint["name"],
                    "description": role_blueprint["description"],
                    "is_cashier": role_blueprint["flags"]["is_cashier"],
                    "is_store_manager": role_blueprint["flags"]["is_store_manager"],
                },
            )
            role.name = role_blueprint["name"]
            role.description = role_blueprint["description"]
            role.is_cashier = role_blueprint["flags"]["is_cashier"]
            role.is_store_manager = role_blueprint["flags"]["is_store_manager"]
            role.save(update_fields=["name", "description", "is_cashier", "is_store_manager"])

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
                    "flags": role_blueprint["flags"],
                }
            )

        return seeded_roles

    @staticmethod
    def serializeUser(user: User):
        user_data = serializeModelInstance(user)
        for key in [
            "username",
            "password",
            "first_name",
            "last_name",
            "groups",
            "user_permissions",
        ]:
            user_data.pop(key, None)

        return {
            **user_data,
            "permissions": sorted(list(get_user_permission_codenames(user))),
            "role": AccountsService.serializeRole(user.role) if getattr(user, "role", None) else None,
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
            "business_settings": BusinessSettingService.buildSessionSettings(user),
        }

    @staticmethod
    def getDefaultRoleBlueprint():
        return {
            "permissions": AccountsService.buildPermissionDefinitions(),
            "roles": ROLE_CATALOG,
        }

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
    def getGoogleClientIds():
        raw = os.getenv("GOOGLE_CLIENT_IDS", "").strip()
        single = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        values = []
        if raw:
            values.extend([item.strip() for item in raw.split(",") if item.strip()])
        if single:
            values.append(single)
        return list(dict.fromkeys(values))

    @staticmethod
    def verifyGoogleIdToken(encoded_token: str):
        client_ids = AccountsService.getGoogleClientIds()
        if not client_ids:
            raise api_error(
                500,
                ErrorCodes.GOOGLE_CLIENT_ID_NOT_CONFIGURED,
                "Google client ID is not configured on the server.",
            )

        request_adapter = google_requests.Request()
        try:
            token_info = google_id_token.verify_oauth2_token(
                encoded_token,
                request_adapter,
                client_ids[0] if len(client_ids) == 1 else None,
            )
        except ValueError:
            raise api_error(401, ErrorCodes.INVALID_GOOGLE_ID_TOKEN, "Invalid Google ID token.")

        audience = token_info.get("aud")
        issuer = token_info.get("iss")
        if audience not in client_ids:
            raise api_error(
                401,
                ErrorCodes.GOOGLE_TOKEN_AUDIENCE_INVALID,
                "Google ID token audience is not allowed.",
            )
        if issuer not in ["accounts.google.com", "https://accounts.google.com"]:
            raise api_error(
                401,
                ErrorCodes.GOOGLE_TOKEN_ISSUER_INVALID,
                "Google ID token issuer is invalid.",
            )

        return token_info

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
    def initializeUserWorkspace(
        email: str = "",
        phone: str = "",
        full_name: str = "",
        provider: str = "otp",
        google_sub: str = "",
        profile_image: str = "",
    ):
        placeholder_company_name = "Enter your company name"
        branch_name = "Main Branch"

        company_code = AccountsService.generateUniqueCode(Company, placeholder_company_name)
        company = Company.objects.create(
            name=placeholder_company_name,
            legal_name=placeholder_company_name,
            code=company_code,
            email=email,
            phone=phone,
        )

        branch_code = AccountsService.generateUniqueCode(Branch, branch_name, company.id)
        branch = Branch.objects.create(
            company_id=company.id,
            name=branch_name,
            code=branch_code,
            phone=phone,
            is_head_office=True,
        )

        AccountsService.seedDefaultRoles(company)
        BusinessSettingService.ensureCompanySettings(company)
        PaymentTypeService.ensureDefaultPaymentTypes(company, branch)
        ExpenseCategoryService.ensureDefaultCategories(company, branch)
        RegisterService.ensureDefaultRegister(company, branch)
        role = Role.objects.filter(company_id=company.id, code="administrator").first()
        if role is None:
            raise api_error(
                500,
                ErrorCodes.SERVER_ERROR,
                "Default administrator role could not be created.",
            )

        username = f"superadmin-{company_code}"

        user = User(
            username=username,
            email=email,
            phone=phone,
            full_name=full_name or "Super Admin",
            profile_image=profile_image,
            company=company,
            branch=branch,
            role=role,
            auth_provider=provider,
            google_sub=google_sub or None,
            is_phone_verified=bool(phone and provider == "otp"),
            is_email_verified=bool(email and provider == "google"),
            onboarding_completed=False,
            is_staff=True,
            is_superuser=True,
            is_store_manager=True,
        )
        user.set_unusable_password()
        user.save()
        return user

    @staticmethod
    def sendOtp(payload):
        existing_user = User.objects.filter(phone=payload.phone).exists()
        purpose = "login" if existing_user else "signup"

        code = f"{random.randint(100000, 999999)}"
        expires_at = timezone.now() + timedelta(minutes=10)

        OtpRequest.objects.filter(phone=payload.phone, verified_at__isnull=True, status=0).update(
            status=1,
            deleted_at=timezone.now(),
        )

        otp_request = commonQuery.createRecord(
            OtpRequest,
            {
                "phone": payload.phone,
                "code": code,
                "purpose": purpose,
                "expires_at": expires_at,
            },
            tenant_config={},
        )

        return {
            "phone": otp_request["phone"],
            "purpose": otp_request["purpose"],
            "expires_at": otp_request["expires_at"],
            "otp_code": otp_request["code"],
            "message": "OTP generated successfully.",
        }

    @staticmethod
    def verifyOtp(request, payload):
        otp_request = (
            OtpRequest.objects.filter(
                phone=payload.phone,
                code=payload.code,
                verified_at__isnull=True,
                status=0,
            )
            .order_by("-created_at")
            .first()
        )

        if otp_request is None:
            raise api_error(400, ErrorCodes.INVALID_OTP, "Invalid OTP.")
        if otp_request.is_expired:
            otp_request.status = 1
            otp_request.deleted_at = timezone.now()
            otp_request.save(update_fields=["status", "deleted_at"])
            raise api_error(400, ErrorCodes.OTP_EXPIRED, "OTP has expired.")

        otp_request.verified_at = timezone.now()
        otp_request.save(update_fields=["verified_at", "updated_at"])

        return AccountsService.identityLogin(
            request,
            type(
                "OtpIdentityPayload",
                (),
                {
                    "provider": "otp",
                    "provider_user_id": None,
                    "phone": payload.phone,
                    "email": "",
                    "full_name": getattr(payload, "full_name", "") or "",
                    "profile_image": "",
                    "device_name": payload.device_name or "",
                },
            )(),
        )

    @staticmethod
    def identityLogin(request, payload):
        provider = (payload.provider or "").lower().strip()
        if provider not in ["otp", "google"]:
            raise api_error(
                400,
                ErrorCodes.UNSUPPORTED_PROVIDER,
                "Supported providers are otp and google.",
            )

        if provider == "otp" and not payload.phone:
            raise api_error(400, ErrorCodes.PHONE_REQUIRED, "Phone is required for OTP login.")
        if provider == "google" and not payload.provider_user_id:
            raise api_error(
                400,
                ErrorCodes.PROVIDER_USER_ID_REQUIRED,
                "provider_user_id is required for Google login.",
            )

        user = None
        if provider == "google":
            user = User.objects.filter(google_sub=payload.provider_user_id).select_related("role").first()
            if user is None and payload.email:
                user = User.objects.filter(email__iexact=payload.email).select_related("role").first()
        elif provider == "otp":
            user = User.objects.filter(phone=payload.phone).select_related("role").first()

        with transaction.atomic():
            if user is None:
                user = AccountsService.initializeUserWorkspace(
                    email=payload.email,
                    phone=payload.phone,
                    full_name=payload.full_name,
                    provider=provider,
                    google_sub=payload.provider_user_id or "",
                    profile_image=getattr(payload, "profile_image", "") or "",
                )
            else:
                updated_fields = []
                if payload.full_name and user.full_name != payload.full_name:
                    user.full_name = payload.full_name
                    updated_fields.append("full_name")
                if payload.email and not user.email:
                    user.email = payload.email
                    updated_fields.append("email")
                if payload.phone and not user.phone:
                    user.phone = payload.phone
                    updated_fields.append("phone")
                if getattr(payload, "profile_image", "") and not user.profile_image:
                    user.profile_image = payload.profile_image
                    updated_fields.append("profile_image")
                if provider == "google" and payload.provider_user_id and user.google_sub != payload.provider_user_id:
                    user.google_sub = payload.provider_user_id
                    updated_fields.append("google_sub")
                if provider == "google" and user.is_email_verified is False and payload.email:
                    user.is_email_verified = True
                    updated_fields.append("is_email_verified")
                if provider == "otp" and user.is_phone_verified is False and payload.phone:
                    user.is_phone_verified = True
                    updated_fields.append("is_phone_verified")
                if updated_fields:
                    user.save(update_fields=updated_fields)

        return AccountsService.issueAccessToken(user, payload.device_name or "", request)

    @staticmethod
    def googleLogin(request, payload):
        if not payload.id_token:
            raise api_error(
                400,
                ErrorCodes.GOOGLE_ID_TOKEN_REQUIRED,
                "id_token is required for Google login.",
            )

        token_info = AccountsService.verifyGoogleIdToken(payload.id_token)

        normalized_payload = type(
            "GoogleIdentityPayload",
            (),
            {
                "provider": "google",
                "provider_user_id": token_info.get("sub"),
                "phone": payload.phone or "",
                "email": token_info.get("email", "") or payload.email or "",
                "full_name": token_info.get("name", "") or payload.full_name or "",
                "profile_image": token_info.get("picture", "") or getattr(payload, "profile_image", "") or "",
                "device_name": payload.device_name or "",
            },
        )()
        return AccountsService.identityLogin(request, normalized_payload)

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
            "sales.ExchangeOrderLink",
            "payments.RefundPayment",
            "sales.ReturnItemTax",
            "sales.ReturnItem",
            "sales.ReturnOrder",
            "payments.SalePayment",
            "promotions.AppliedCoupon",
            "sales.SaleTax",
            "sales.SaleCoupon",
            "sales.SaleStorage",
            "sales.SaleSetting",
            "sales.SaleAddress",
            "sales.SaleNote",
            "sales.InstallmentLine",
            "sales.InstallmentPlan",
            "sales.SaleItem",
            "sales.SaleOrder",
            "sales.CartDraft",
            "purchases.PurchasePayment",
            "purchases.PurchaseItem",
            "purchases.PurchaseOrder",
            "inventory.StockLedger",
            "inventory.StockLot",
            "inventory.StockTransferItem",
            "inventory.StockTransfer",
            "inventory.StockAdjustment",
            "inventory.LowStockAlert",
            "registers.CashRegisterEntry",
            "reports.DayClosing",
            "expenses.ExpenseEntry",
            "registers.CashierShift",
            "catalog.ProductHistoryCombined",
            "catalog.ProductHistory",
            "catalog.ProductTax",
            "catalog.ProductUnitQuantity",
            "catalog.ProductSubItem",
            "catalog.ProductGallery",
            "promotions.CustomerCoupon",
            "rewards.RewardRedemption",
            "rewards.CustomerRewardBalance",
            "rewards.RewardRule",
            "rewards.RewardSystem",
            "promotions.CouponProduct",
            "promotions.CouponCategory",
            "promotions.CouponCustomer",
            "promotions.CouponCustomerGroup",
            "promotions.Coupon",
            "customers.CustomerWalletTransaction",
            "customers.CustomerCreditLedger",
            "customers.CustomerAccountHistory",
            "customers.CustomerAddress",
            "customers.Customer",
            "customers.CustomerGroup",
            "catalog.Product",
            "catalog.Tax",
            "catalog.TaxGroup",
            "catalog.Unit",
            "catalog.UnitGroup",
            "catalog.Brand",
            "catalog.Category",
            "catalog.ScaleRange",
            "accounting.TransactionHistory",
            "accounting.ActiveTransactionHistory",
            "accounting.Transaction",
            "accounting.TransactionBalanceDay",
            "accounting.TransactionBalanceMonth",
            "accounting.TransactionActionRule",
            "accounting.TransactionAccount",
            "expenses.ExpenseCategory",
            "payments.PaymentType",
            "registers.CashRegister",
            "settingsapi.Setting",
            "settingsapi.Option",
            "settingsapi.BusinessSetting",
            "reports.SalesSummarySnapshot",
            "reports.DashboardDay",
            "reports.DashboardMonth",
            "notifications.Notification",
            "mediahub.Media",
            "audit.AuditLog",
            "accounts.UserRoleRelation",
            "accounts.PermissionAccess",
            "accounts.UserScope",
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
        phones = [
            phone
            for phone in User.objects.filter(id__in=user_ids)
            .exclude(phone="")
            .values_list("phone", flat=True)
        ]
        branch_ids = list(
            Branch.objects.filter(company_id=company.id).values_list("id", flat=True)
        )
        role_ids = list(
            Role.objects.filter(company_id=company.id).values_list("id", flat=True)
        )

        with transaction.atomic():
            token_count, _ = AccessToken.objects.filter(user_id__in=user_ids).delete()
            user_attribute_model = apps.get_model("accounts", "UserAttribute")
            user_widget_model = apps.get_model("accounts", "UserWidget")
            user_attribute_count, _ = user_attribute_model.objects.filter(user_id__in=user_ids).delete()
            user_widget_count, _ = user_widget_model.objects.filter(user_id__in=user_ids).delete()
            tenant_deleted_summary = AccountsService._deleteCompanyScopedModels(company.id)
            deleted_user_count, _ = User.objects.filter(id__in=user_ids).delete()
            deleted_otp_count, _ = OtpRequest.objects.filter(phone__in=phones).delete()
            deleted_company_count, _ = Company.objects.filter(id=company.id).delete()

        return {
            "company_id": company.id,
            "branch_ids": branch_ids,
            "role_ids": role_ids,
            "user_ids": user_ids,
            "deleted_access_token_count": token_count,
            "deleted_user_attribute_count": user_attribute_count,
            "deleted_user_widget_count": user_widget_count,
            "deleted_tenant_records": tenant_deleted_summary,
            "deleted_company_count": deleted_company_count,
            "deleted_user_count": deleted_user_count,
            "deleted_otp_count": deleted_otp_count,
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
                    "full_name",
                    "phone",
                    "email",
                    "branch_id",
                    "branch__name",
                    "role_id",
                    "role__name",
                    "auth_provider",
                    "is_cashier",
                    "is_store_manager",
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
            role = Role.objects.filter(company_id=user.company_id, id=role_id, status__in=[0, 1]).first()
            if role is None:
                raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")

        full_name = data.get("full_name") or "Staff User"
        phone = data.get("phone") or ""
        email = data.get("email") or ""
        validateUniqueFields(
            User,
            {"phone": phone, "email": email},
            scope="global",
            status_in=(0, 1),
            case_insensitive=["email"],
            messages={"phone": "Phone already exists.", "email": "Email already exists."},
        )

        target_user = User(
            username=f"user-{secrets.token_hex(8)}",
            company_id=user.company_id,
            branch=branch,
            role=role,
            full_name=full_name,
            phone=phone,
            email=email,
            auth_provider="otp" if phone else "google",
            is_cashier=role.is_cashier if role else False,
            is_store_manager=role.is_store_manager if role else False,
            status=data.get("status", 0),
        )
        target_user.set_unusable_password()
        target_user.save()
        return AccountsService.serializeUser(target_user)

    @staticmethod
    def updateUser(user: User, user_id: int, payload):
        target_user = User.objects.filter(company_id=user.company_id, id=user_id, status__in=[0, 1]).first()
        if target_user is None:
            raise api_error(404, ErrorCodes.USER_NOT_FOUND, "User not found.")

        data = payload.dict(exclude_unset=True)
        validateUniqueFields(
            User,
            {"phone": data.get("phone"), "email": data.get("email")},
            scope="global",
            exclude_id=user_id,
            status_in=(0, 1),
            case_insensitive=["email"],
            messages={"phone": "Phone already exists.", "email": "Email already exists."},
        )
        if data.get("branch_id"):
            branch = Branch.objects.filter(company_id=user.company_id, id=data["branch_id"], status__in=[0, 1]).first()
            if branch is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")
            target_user.branch = branch
        if data.get("role_id"):
            role = Role.objects.filter(company_id=user.company_id, id=data["role_id"], status__in=[0, 1]).first()
            if role is None:
                raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")
            target_user.role = role
            target_user.is_cashier = role.is_cashier
            target_user.is_store_manager = role.is_store_manager

        for field in ["full_name", "phone", "email"]:
            if field in data:
                setattr(target_user, field, data[field] or "")
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
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
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
            Role.objects.filter(company_id=user.company_id, status__in=[0, 1])
            .prefetch_related("permissions")
            .order_by("name")
        )
        return [AccountsService.serializeRole(role) for role in roles]

    @staticmethod
    def getRole(user: User, role_id: int):
        AccountsService.ensurePermissions()
        role = (
            Role.objects.filter(company_id=user.company_id, id=role_id, status__in=[0, 1])
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

        role_code = slugify(payload.code or payload.name)
        validateUniqueFields(
            Role,
            {"code": role_code},
            scope=None,
            status_in=(0, 1),
            extra_filters={"company_id": user.company_id},
            messages={"code": "Role code already exists."},
        )

        role = Role.objects.create(
            company_id=user.company_id,
            name=payload.name,
            code=role_code,
            description=payload.description,
            is_cashier=payload.is_cashier,
            is_store_manager=payload.is_store_manager,
        )
        role.permissions.set([permission_map[code] for code in requested_permissions])
        return AccountsService.serializeRole(role)

    @staticmethod
    def updateRole(user: User, role_id: int, payload):
        role = (
            Role.objects.filter(company_id=user.company_id, id=role_id, status__in=[0, 1])
            .prefetch_related("permissions")
            .first()
        )
        if role is None:
            raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")

        data = payload.dict(exclude_unset=True)
        permission_codenames = data.pop("permission_codenames", None)

        if "code" in data and data["code"]:
            data["code"] = slugify(data["code"])
            validateUniqueFields(
                Role,
                {"code": data["code"]},
                scope=None,
                exclude_id=role_id,
                status_in=(0, 1),
                extra_filters={"company_id": user.company_id},
                messages={"code": "Role code already exists."},
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
        role = Role.objects.filter(company_id=user.company_id, id=role_id, status__in=[0, 1]).first()
        if role is None:
            raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")
        if role.code == "administrator":
            raise api_error(
                400,
                ErrorCodes.ADMINISTRATOR_ROLE_DELETE_FORBIDDEN,
                "Administrator role cannot be deleted.",
            )
        if role.users.filter(status__in=[0, 1]).exists():
            raise api_error(
                400,
                ErrorCodes.ROLE_IN_USE,
                "This role is assigned to active users and cannot be deleted.",
            )

        deleted = commonQuery.softDeleteById(
            Role,
            {"id": role_id, "company_id": user.company_id},
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

        role = Role.objects.filter(company_id=user.company_id, id=role_id, status__in=[0, 1]).first()
        if role is None:
            raise api_error(404, ErrorCodes.ROLE_NOT_FOUND, "Role not found.")

        target_user.role = role
        target_user.is_cashier = role.is_cashier
        target_user.is_store_manager = role.is_store_manager
        target_user.save(update_fields=["role", "is_cashier", "is_store_manager"])
        return AccountsService.serializeUser(target_user)
