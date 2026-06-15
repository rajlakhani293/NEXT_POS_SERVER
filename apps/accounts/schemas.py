# type: ignore
from datetime import datetime
from typing import List, Optional

from ninja import Schema
from apps.common.schemas import ActiveStatus
from pydantic import Field


class LoginIn(Schema):
    username: str = Field(..., min_length=3, example="storeadmin")
    password: str = Field(..., min_length=8, example="StrongPassword123!")
    device_name: Optional[str] = Field("", example="Owner Laptop")


class RegisterIn(Schema):
    username: str = Field(..., min_length=3, example="storeadmin")
    email: str = Field(..., example="owner@example.com")
    password: str = Field(..., min_length=8, example="StrongPassword123!")
    password_confirm: str = Field(..., min_length=8, example="StrongPassword123!")
    device_name: Optional[str] = Field("", example="Owner Laptop")


class SendOtpIn(Schema):
    phone: str = Field(..., description="Phone number that will receive or simulate the OTP.", example="9999999999")


class VerifyOtpIn(Schema):
    phone: str = Field(..., description="Phone number used for OTP generation.", example="9999999999")
    code: str = Field(..., description="Six digit OTP code returned by send-otp in development mode.", example="123456")
    device_name: Optional[str] = Field("", description="Readable device label for the session.", example="Main Counter")


class UserOut(Schema):
    id: int
    username: str
    email: str = ""
    full_name: str = ""
    profile_image: str = ""
    phone: str = ""
    theme: str = "light"
    language: str = "en"
    company_id: Optional[int] = None
    branch_id: Optional[int] = None
    role_id: Optional[int] = None
    is_cashier: bool
    is_store_manager: bool
    status: int


class RoleIn(Schema):
    name: str = Field(..., example="Branch Supervisor")
    code: str = Field(..., example="branch-supervisor")
    description: str = Field("", example="Handles branch sales and approvals.")
    is_cashier: bool = Field(False, example=False)
    is_store_manager: bool = Field(False, example=True)
    permission_codenames: List[str] = Field(default_factory=list, example=["sales_view", "sales_create", "returns_approve"])


class RoleUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_cashier: Optional[bool] = None
    is_store_manager: Optional[bool] = None
    permission_codenames: Optional[List[str]] = None


class RoleAssignIn(Schema):
    role_id: int = Field(..., example=2)


class BranchSwitchIn(Schema):
    branch_id: int = Field(..., example=1)


class UserIn(Schema):
    username: str = Field(..., min_length=3, example="counterstaff")
    password: str = Field(..., min_length=8, example="StrongPassword123!")
    full_name: str = Field(..., example="Counter Staff")
    phone: str = Field("", example="9999999999")
    email: str = Field("", example="staff@example.com")
    branch_id: Optional[int] = None
    role_id: Optional[int] = None
    status: int = 0


class UserUpdateIn(Schema):
    username: Optional[str] = Field(None, min_length=3)
    password: Optional[str] = Field(None, min_length=8)
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    branch_id: Optional[int] = None
    role_id: Optional[int] = None
    status: Optional[ActiveStatus] = None


class LoginOut(Schema):
    token: str
    expires_at: datetime
    user: UserOut


class MessageOut(Schema):
    message: str


class IdentityAuthIn(Schema):
    provider: str = Field(..., description="Identity provider. Use 'google' for Google Sign-In and 'otp' for OTP completion.", example="google")
    id_token: Optional[str] = Field(
        None,
        description="Verified Google ID token returned by Google Sign-In on the frontend. Required for google-login.",
        example="eyJhbGciOiJSUzI1NiIsImtpZCI6Ij...google-id-token...",
    )
    provider_user_id: Optional[str] = Field(
        None,
        description="Provider-specific subject identifier. Usually filled by the backend after Google token verification.",
        example="117200475532672775645",
    )
    phone: str = Field("", description="Phone number, mainly used by OTP-based onboarding.", example="9999999999")
    email: str = Field("", description="Fallback email if already known. Google login normally fills this from the verified token.", example="raj@example.com")
    full_name: str = Field("", description="Fallback full name if already known. Google login normally fills this from the verified token.", example="Raj Patel")
    profile_image: str = Field("", description="Fallback avatar URL if already known. Google login normally fills this from the verified token picture.", example="https://lh3.googleusercontent.com/a/default-user")
    device_name: Optional[str] = Field("", description="Readable device label for the session.", example="Owner Laptop")


class GoogleLoginIn(Schema):
    provider: str = Field(
        "google",
        description="Frontend provider identifier. Keep this value as 'google'.",
        example="google",
    )
    id_token: str = Field(
        ...,
        description="Google ID token returned by the frontend Google Sign-In flow. Send this exact token to the backend for server-side verification.",
        example="eyJhbGciOiJSUzI1NiIsImtpZCI6Ij...google-id-token...",
    )
    phone: str = Field(
        "",
        description="Optional phone number if your frontend/provider already has one. Google ID token usually does not include phone.",
        example="9999999999",
    )
    device_name: Optional[str] = Field(
        "",
        description="Readable device label for the current sign-in, such as browser, laptop, or counter name.",
        example="Owner Laptop",
    )
