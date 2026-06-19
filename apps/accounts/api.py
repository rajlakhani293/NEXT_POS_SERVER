from typing import Optional
from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.accounts.schemas import (
    BranchSwitchIn,
    LoginIn,
    PermissionAccessApproveIn,
    PermissionAccessRequestIn,
    RegisterIn,
    RoleAssignIn,
    RoleIn,
    RoleUpdateIn,
    UserIn,
    UserUpdateIn,
)
from apps.accounts.services import AccountsService
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema


router = Router(tags=["accounts"])


@router.get("/defaults/roles", response=ApiResponse)
def defaultRoles(request):
    """Return the default retail role and permission blueprint used during company setup."""
    data = AccountsService.getDefaultRoleBlueprint()
    return successResponse("Default role blueprint fetched successfully.", data=data)


@router.post("/register", response=ApiResponse)
def register(request, payload: RegisterIn):
    data = AccountsService.register(request, payload)
    return successResponse("Account created successfully.", data=data)


@router.post("/login", response=ApiResponse)
def login(request, payload: LoginIn):
    data = AccountsService.login(request, payload)
    return successResponse("You have been successfully connected.", data=data)


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


@router.post("/switch-branch", auth=auth_bearer, response=ApiResponse)
def switchBranch(request, payload: BranchSwitchIn):
    """Switch the active branch and issue a fresh token for the new branch context."""
    token_value = request.auth.get("token")
    data = AccountsService.switchBranch(request.user, payload.branch_id, request, token_value)
    return successResponse("Branch switched successfully.", data=data)


@router.delete("/workspace", auth=auth_bearer, response=ApiResponse)
def deleteWorkspace(request):
    """Delete the current signup-created workspace and its tenant data."""
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


@router.post("/permissions-access/request", auth=auth_bearer, response=ApiResponse)
def requestPermissionAccess(request, payload: PermissionAccessRequestIn):
    data = AccountsService.requestPermissionAccess(request.user, payload.dict())
    return successResponse("Permission access request processed successfully.", data=data)


@router.post("/permissions-access/get-transactions", auth=auth_bearer, response=ApiResponse)
@permission_required("permissions_access_view")
def listPermissionAccess(request, payload: Optional[dict] = None):
    data = AccountsService.listPermissionAccess(request.user, payload)
    return successResponse("Permission access records fetched successfully.", data=data)


@router.post("/permissions-access/{access_id}/approve", auth=auth_bearer, response=ApiResponse)
def approvePermissionAccess(request, access_id: int, payload: PermissionAccessApproveIn):
    data = AccountsService.approvePermissionAccess(request.user, access_id, payload.dict())
    return successResponse("Permission access granted successfully.", data=data)


@router.post("/permissions-access/{access_id}/used", auth=auth_bearer, response=ApiResponse)
def markPermissionAccessUsed(request, access_id: int):
    data = AccountsService.markPermissionAccessUsed(request.user, access_id)
    return successResponse("Permission access marked as used successfully.", data=data)


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
def deleteUsers(request, payload: BulkIdsSchema):
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
