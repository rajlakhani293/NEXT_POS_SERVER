from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.accounts.controllers import AccountsController
from apps.accounts.schemas import GoogleLoginIn, IdentityAuthIn, RoleAssignIn, RoleIn, RoleUpdateIn, SendOtpIn, VerifyOtpIn
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse


router = Router(tags=["accounts"])


@router.get("/defaults/roles", response=ApiResponse)
def defaultRoles(request):
    """Return the default retail role and permission blueprint used during company setup."""
    return AccountsController.defaultRoles(request)


@router.post("/send-otp", response=ApiResponse)
def sendOtp(request, payload: SendOtpIn):
    """Generate an OTP code for login or signup. Returns the code directly for development use."""
    return AccountsController.sendOtp(request, payload)


@router.post("/verify-otp", response=ApiResponse)
def verifyOtp(request, payload: VerifyOtpIn):
    """Verify a locally generated OTP and complete login or signup with auto-onboarding."""
    return AccountsController.verifyOtp(request, payload)


@router.post("/identity-login", response=ApiResponse)
def identityLogin(request, payload: IdentityAuthIn):
    """Complete login/signup after an external identity provider has already verified the user."""
    return AccountsController.identityLogin(request, payload)


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
    return AccountsController.googleLogin(request, payload)


@router.get("/me", auth=auth_bearer, response=ApiResponse)
def me(request):
    """Return the authenticated user with role and effective permissions."""
    return AccountsController.me(request)


@router.post("/logout", auth=auth_bearer, response=ApiResponse)
def logout(request):
    """Revoke the current access token."""
    return AccountsController.logout(request)


@router.delete("/workspace", auth=auth_bearer, response=ApiResponse)
def deleteWorkspace(request):
    """Delete the current signup-created workspace including company, branches, tenant data, users, roles, tokens, and OTP records."""
    return AccountsController.deleteWorkspace(request)


@router.get("/roles", auth=auth_bearer, response=ApiResponse)
@permission_required("roles_view")
def listRoles(request):
    """List roles for the current company."""
    return AccountsController.listRoles(request)


@router.post("/roles", auth=auth_bearer, response=ApiResponse)
@permission_required("roles_create")
def createRole(request, payload: RoleIn):
    """Create a new company-scoped role with assigned permissions."""
    return AccountsController.createRole(request, payload)


@router.put("/roles/{role_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("roles_update")
def updateRole(request, role_id: int, payload: RoleUpdateIn):
    """Update a role and its permission set."""
    return AccountsController.updateRole(request, role_id, payload)


@router.delete("/roles/{role_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("roles_delete")
def deleteRole(request, role_id: int):
    """Soft delete a company role if it is not in active use."""
    return AccountsController.deleteRole(request, role_id)


@router.post("/users/{user_id}/assign-role", auth=auth_bearer, response=ApiResponse)
@permission_required("users_update")
def assignRole(request, user_id: int, payload: RoleAssignIn):
    """Assign a role to a user and sync cashier/manager flags."""
    return AccountsController.assignRole(request, user_id, payload)
