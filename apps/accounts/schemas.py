# type: ignore
from datetime import datetime
from decimal import Decimal
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
    namespace: str = Field(..., example="nexopos.branch.supervisor")
    description: str = Field("", example="Handles branch sales and approvals.")
    reward_system_id: Optional[int] = None
    minimal_credit_payment: Decimal = Field(Decimal("0"), ge=0)
    locked: bool = True
    permission_codenames: List[str] = Field(default_factory=list, example=["sales_view", "sales_create", "returns_approve"])


class RoleUpdateIn(Schema):
    name: Optional[str] = None
    namespace: Optional[str] = None
    description: Optional[str] = None
    reward_system_id: Optional[int] = None
    minimal_credit_payment: Optional[Decimal] = Field(None, ge=0)
    locked: Optional[bool] = None
    permission_codenames: Optional[List[str]] = None


class RoleAssignIn(Schema):
    role_id: int = Field(..., example=2)


class BranchSwitchIn(Schema):
    branch_id: int = Field(..., example=1)


class PermissionAccessRequestIn(Schema):
    permission: str = Field(..., example="cart_product_discount")
    url: Optional[str] = Field(None, example="/sales/create")


class PermissionAccessApproveIn(Schema):
    permission: str = Field(..., example="cart_product_discount")


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
