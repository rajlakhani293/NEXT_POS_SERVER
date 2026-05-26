# type: ignore
import secrets
import random
import os
from datetime import timedelta
from typing import Optional

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
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
from apps.common.helpers import serializeModelInstance
from apps.organizations.models import Branch, Company


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
            role = Role.objects.create(
                company_id=company.id,
                name=role_blueprint["name"],
                code=role_blueprint["code"],
                description=role_blueprint["description"],
                is_cashier=role_blueprint["flags"]["is_cashier"],
                is_store_manager=role_blueprint["flags"]["is_store_manager"],
            )

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
        return AccountsService.serializeUser(user)

    @staticmethod
    def logout(token_value: str):
        AccessToken.objects.filter(token=token_value).update(
            status=2,
            deleted_at=timezone.now(),
        )
        return {"logged_out": True}

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
            deleted_company_count, _ = Company.objects.filter(id=company.id).delete()
            deleted_user_count, _ = User.objects.filter(id__in=user_ids).delete()
            deleted_otp_count, _ = OtpRequest.objects.filter(phone__in=phones).delete()

        return {
            "company_id": company.id,
            "branch_ids": branch_ids,
            "role_ids": role_ids,
            "user_ids": user_ids,
            "deleted_company_count": deleted_company_count,
            "deleted_user_count": deleted_user_count,
            "deleted_otp_count": deleted_otp_count,
            "note": "Shared Django permission definitions are global and were not deleted.",
        }

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

        role = Role.objects.create(
            company_id=user.company_id,
            name=payload.name,
            code=slugify(payload.code or payload.name),
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
