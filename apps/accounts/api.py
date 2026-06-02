from typing import Optional
from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.accounts.schemas import GoogleLoginIn, IdentityAuthIn, RoleAssignIn, RoleIn, RoleUpdateIn, SendOtpIn, UserIn, UserUpdateIn, VerifyOtpIn
from apps.accounts.services import AccountsService
from apps.catalog.schemas import DeleteSchema, StatusUpdateSchema
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse


router = Router(tags=["accounts"])


@router.get("/defaults/roles", response=ApiResponse)
def defaultRoles(request):
    """Return the default retail role and permission blueprint used during company setup."""
    data = AccountsService.getDefaultRoleBlueprint()
    return successResponse("Default role blueprint fetched successfully.", data=data)


@router.post("/send-otp", response=ApiResponse)
def sendOtp(request, payload: SendOtpIn):
    """Generate an OTP code for login or signup. Returns the code directly for development use."""
    data = AccountsService.sendOtp(payload)
    return successResponse("OTP generated successfully.", data=data)


@router.post("/verify-otp", response=ApiResponse)
def verifyOtp(request, payload: VerifyOtpIn):
    """Verify a locally generated OTP and complete login or signup with auto-onboarding."""
    data = AccountsService.verifyOtp(request, payload)
    return successResponse("OTP verified successfully.", data=data)


@router.post("/identity-login", response=ApiResponse)
def identityLogin(request, payload: IdentityAuthIn):
    """Complete login/signup after an external identity provider has already verified the user."""
    data = AccountsService.identityLogin(request, payload)
    return successResponse("Identity login successful.", data=data)


@router.post("/google-login", response=ApiResponse)
def googleLogin(request, payload: GoogleLoginIn):
    """Frontend Google Sign-In contract.

    Frontend flow:
    1. Complete Google Sign-In in the browser or app.
    2. Read the Google `credential` / ID token from Google.
    3. Send it here as:
       {
         "provider": "google",
         "id_token": "<google-id-token>",
         "device_name": "Owner Laptop"
       }

    Backend flow:
    - verify the ID token with Google
    - create or find the user
    - auto-create placeholder company and Main Branch when the user is new
    - return your app bearer token for future API requests
    """
    data = AccountsService.googleLogin(request, payload)
    return successResponse("Google login successful.", data=data)


@router.get("/session-data", auth=auth_bearer, response=ApiResponse)
def sessionData(request):
    """Return the authenticated user with role and effective permissions."""
    data = AccountsService.currentUser(request.user)
    return successResponse("Session data fetched successfully.", data=data)


@router.post("/logout", auth=auth_bearer, response=ApiResponse)
def logout(request):
    """Revoke the current access token."""
    token_value = request.auth.get("token")
    AccountsService.logout(token_value)
    return successResponse("Logged out successfully.")


@router.delete("/workspace", auth=auth_bearer, response=ApiResponse)
def deleteWorkspace(request):
    """Delete the current signup-created workspace including company, branches, tenant data, users, roles, tokens, and OTP records."""
    data = AccountsService.deleteWorkspace(request.user)
    return successResponse("Workspace deleted successfully.", data=data)


@router.get("/roles", auth=auth_bearer, response=ApiResponse)
@permission_required("roles_view")
def listRoles(request):
    """List roles for the current company."""
    data = AccountsService.listRoles(request.user)
    return successResponse("Roles fetched successfully.", data=data)


@router.get("/permissions", auth=auth_bearer, response=ApiResponse)
@permission_required("roles_view")
def listPermissions(request):
    data = AccountsService.buildPermissionDefinitions()
    return successResponse("Permissions fetched successfully.", data=data)


@router.post("/roles", auth=auth_bearer, response=ApiResponse)
@permission_required("roles_create")
def createRole(request, payload: RoleIn):
    """Create a new company-scoped role with assigned permissions."""
    data = AccountsService.createRole(request.user, payload)
    return successResponse("Role created successfully.", data=data)


@router.get("/roles/{role_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("roles_view")
def getRoleById(request, role_id: int):
    """Return one company role with assigned permissions."""
    data = AccountsService.getRole(request.user, role_id)
    return successResponse("Role fetched successfully.", data=data)


@router.put("/roles/{role_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("roles_update")
def updateRole(request, role_id: int, payload: RoleUpdateIn):
    """Update a role and its permission set."""
    data = AccountsService.updateRole(request.user, role_id, payload)
    return successResponse("Role updated successfully.", data=data)


@router.delete("/roles/{role_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("roles_delete")
def deleteRole(request, role_id: int):
    """Soft delete a company role if it is not in active use."""
    data = AccountsService.deleteRole(request.user, role_id)
    return successResponse("Role deleted successfully.", data=data)


@router.post("/users/{user_id}/assign-role", auth=auth_bearer, response=ApiResponse)
@permission_required("users_update")
def assignRole(request, user_id: int, payload: RoleAssignIn):
    """Assign a role to a user and sync cashier/manager flags."""
    data = AccountsService.assignRole(request.user, user_id, payload.role_id)
    return successResponse("Role assigned successfully.", data=data)


@router.post("/users/", auth=auth_bearer, response=ApiResponse)
@permission_required("users_create")
def createUser(request, payload: UserIn):
    data = AccountsService.createUser(request.user, payload)
    return successResponse("User created successfully.", data=data)


@router.post("/users/get-transactions", auth=auth_bearer, response=ApiResponse)
@permission_required("users_view")
def listUsers(request, payload: Optional[dict] = None):
    data = AccountsService.listUsers(request.user, payload)
    return successResponse("Users fetched successfully.", data=data)


@router.get("/users/dropdown-list", auth=auth_bearer, response=ApiResponse)
@permission_required("users_view")
def userDropdown(request):
    data = AccountsService.userDropdown(request.user)
    return successResponse("Dropdown list retrieved successfully.", data=data)


@router.delete("/users/delete", auth=auth_bearer, response=ApiResponse)
@permission_required("users_delete")
def deleteUsers(request, payload: DeleteSchema):
    data = AccountsService.deleteUsers(request.user, payload.dict())
    return successResponse("Users deleted successfully.", data=data)


@router.patch("/users/status", auth=auth_bearer, response=ApiResponse)
@permission_required("users_update")
def updateUserStatus(request, payload: StatusUpdateSchema):
    data = AccountsService.updateUserStatus(request.user, payload.dict())
    return successResponse("User status updated successfully.", data=data)


@router.get("/users/{user_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("users_view")
def getUserById(request, user_id: int):
    data = AccountsService.getUser(request.user, user_id)
    return successResponse("User fetched successfully.", data=data)


@router.put("/users/{user_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("users_update")
def updateUser(request, user_id: int, payload: UserUpdateIn):
    data = AccountsService.updateUser(request.user, user_id, payload)
    return successResponse("User updated successfully.", data=data)
