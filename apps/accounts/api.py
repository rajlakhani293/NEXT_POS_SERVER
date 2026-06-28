from typing import Optional
from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.accounts.models import Role
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
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse, successResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData


router = Router(tags=["accounts"])
sourceRouter = Router(tags=["users"], auth=auth_bearer)


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
@permissionRequired("roles_view")
def listRoles(request):
    """List roles for the current company."""
    data = AccountsService.listRoles(request.user)
    return successResponse("Roles fetched successfully.", data=data)


@router.get("/permissions", auth=auth_bearer, response=ApiResponse)
@permissionRequired("roles_view")
def listPermissions(request):
    data = AccountsService.buildPermissionDefinitions()
    return successResponse("Permissions fetched successfully.", data=data)


@router.post("/permissions-access/request", auth=auth_bearer, response=ApiResponse)
def requestPermissionAccess(request, payload: PermissionAccessRequestIn):
    data = AccountsService.requestPermissionAccess(request.user, payloadData(payload))
    return successResponse("Permission access request processed successfully.", data=data)


@router.post("/permissions-access/get-transactions", auth=auth_bearer, response=ApiResponse)
@permissionRequired("permissions_access_view")
def listPermissionAccess(request, payload: Optional[dict] = None):
    data = AccountsService.listPermissionAccess(request.user, payload)
    return successResponse("Permission access records fetched successfully.", data=data)


@router.post("/permissions-access/{access_id}/approve", auth=auth_bearer, response=ApiResponse)
def approvePermissionAccess(request, access_id: int, payload: PermissionAccessApproveIn):
    data = AccountsService.approvePermissionAccess(request.user, access_id, payloadData(payload))
    return successResponse("Permission access granted successfully.", data=data)


@router.post("/permissions-access/{access_id}/used", auth=auth_bearer, response=ApiResponse)
def markPermissionAccessUsed(request, access_id: int):
    data = AccountsService.markPermissionAccessUsed(request.user, access_id)
    return successResponse("Permission access marked as used successfully.", data=data)


@router.post("/roles", auth=auth_bearer, response=ApiResponse)
@permissionRequired("roles_create")
def createRole(request, payload: RoleIn):
    """Create a new company-scoped role with assigned permissions."""
    data = AccountsService.createRole(request.user, payload)
    return successResponse("Role created successfully.", data=data)


@router.get("/roles/{role_id}", auth=auth_bearer, response=ApiResponse)
@permissionRequired("roles_view")
def getRoleById(request, role_id: int):
    """Return one company role with assigned permissions."""
    data = AccountsService.getRole(request.user, role_id)
    return successResponse("Role fetched successfully.", data=data)


@router.put("/roles/{role_id}", auth=auth_bearer, response=ApiResponse)
@permissionRequired("roles_update")
def updateRole(request, role_id: int, payload: RoleUpdateIn):
    """Update a role and its permission set."""
    data = AccountsService.updateRole(request.user, role_id, payload)
    return successResponse("Role updated successfully.", data=data)


@router.delete("/roles/{role_id}", auth=auth_bearer, response=ApiResponse)
@permissionRequired("roles_delete")
def deleteRole(request, role_id: int):
    """Soft delete a company role if it is not in active use."""
    data = AccountsService.deleteRole(request.user, role_id)
    return successResponse("Role deleted successfully.", data=data)


@router.post("/users/{user_id}/assign-role", auth=auth_bearer, response=ApiResponse)
@permissionRequired("users_update")
def assignRole(request, user_id: int, payload: RoleAssignIn):
    """Assign a role to a user and sync cashier/manager flags."""
    data = AccountsService.assignRole(request.user, user_id, payload.role_id)
    return successResponse("Role assigned successfully.", data=data)


@router.post("/users/", auth=auth_bearer, response=ApiResponse)
@permissionRequired("users_create")
def createUser(request, payload: UserIn):
    data = AccountsService.createUser(request.user, payload)
    return successResponse("User created successfully.", data=data)


@router.post("/users/get-transactions", auth=auth_bearer, response=ApiResponse)
@permissionRequired("users_view")
def listUsers(request, payload: Optional[dict] = None):
    data = AccountsService.listUsers(request.user, payload)
    return successResponse("Users fetched successfully.", data=data)


@router.get("/users/dropdown-list", auth=auth_bearer, response=ApiResponse)
@permissionRequired("users_view")
def userDropdown(request):
    data = AccountsService.userDropdown(request.user)
    return successResponse("Dropdown list retrieved successfully.", data=data)


@router.delete("/users/delete", auth=auth_bearer, response=ApiResponse)
@permissionRequired("users_delete")
def deleteUsers(request, payload: BulkIdsSchema):
    data = AccountsService.deleteUsers(request.user, payloadData(payload))
    return successResponse("Users deleted successfully.", data=data)


@router.patch("/users/status", auth=auth_bearer, response=ApiResponse)
@permissionRequired("users_update")
def updateUserStatus(request, payload: StatusUpdateSchema):
    data = AccountsService.updateUserStatus(request.user, payloadData(payload))
    return successResponse("User status updated successfully.", data=data)


@router.get("/users/{user_id}", auth=auth_bearer, response=ApiResponse)
@permissionRequired("users_view")
def getUserById(request, user_id: int):
    data = AccountsService.getUser(request.user, user_id)
    return successResponse("User fetched successfully.", data=data)


@router.put("/users/{user_id}", auth=auth_bearer, response=ApiResponse)
@permissionRequired("users_update")
def updateUser(request, user_id: int, payload: UserUpdateIn):
    data = AccountsService.updateUser(request.user, user_id, payload)
    return successResponse("User updated successfully.", data=data)


@sourceRouter.get("/user", response=ApiResponse)
def sourceCurrentUser(request):
    return successResponse("User fetched successfully.", data=AccountsService.serializeUser(request.user))


@sourceRouter.get("/user/permissions", response=ApiResponse)
def sourceCurrentUserPermissions(request):
    return successResponse("Permissions fetched successfully.", data=sorted(list(AccountsService.serializeUser(request.user)["permissions"])))


@sourceRouter.post("/user/access/{access_id}", response=ApiResponse)
def sourceApproveAccess(request, access_id: int, payload: PermissionAccessApproveIn):
    data = AccountsService.approvePermissionAccess(request.user, access_id, payloadData(payload))
    return successResponse("Permission access granted successfully.", data=data)


@sourceRouter.get("/user/access/{access_id}", response=ApiResponse)
def sourceGetAccess(request, access_id: int):
    data = AccountsService.listPermissionAccess(request.user, {"filters": 2})
    access = next((item for item in data["items"] if item["id"] == access_id), None)
    return successResponse("Permission access fetched successfully.", data=access)


@sourceRouter.get("/user/access/{access_id}/use", response=ApiResponse)
def sourceMarkAccessUsed(request, access_id: int):
    data = AccountsService.markPermissionAccessUsed(request.user, access_id)
    return successResponse("Permission access marked as used successfully.", data=data)


@sourceRouter.post("/users/create-token", response=ApiResponse)
def sourceCreateToken(request, payload: dict):
    data = AccountsService.createAccessToken(request.user, request, payload or {})
    return successResponse("Token created successfully.", data=data)


@sourceRouter.get("/users/tokens", response=ApiResponse)
def sourceGetTokens(request):
    data = AccountsService.listAccessTokens(request.user)
    return successResponse("Tokens fetched successfully.", data=data)


@sourceRouter.delete("/users/tokens/{token_id}", response=ApiResponse)
def sourceDeleteToken(request, token_id: int):
    data = AccountsService.deleteAccessToken(request.user, token_id)
    return successResponse("Token deleted successfully.", data=data)


@sourceRouter.post("/users/check-permission", response=ApiResponse)
def sourceCheckPermission(request, payload: dict):
    data = AccountsService.checkPermission(request.user, payload or {})
    return successResponse("Permission checked successfully.", data=data)


@sourceRouter.get("/users", response=ApiResponse)
@permissionRequired("users_view")
def sourceGetUsers(request):
    data = AccountsService.listUsers(request.user, {})
    return successResponse("Users fetched successfully.", data=data)


@sourceRouter.get("/users/permissions", response=ApiResponse)
@permissionRequired("users_view")
def sourceGetPermissions(request):
    data = AccountsService.buildPermissionDefinitions()
    return successResponse("Permissions fetched successfully.", data=data)


@sourceRouter.get("/users/roles", response=ApiResponse)
@permissionRequired("roles_view")
def sourceGetRoles(request):
    data = AccountsService.listRoles(request.user)
    return successResponse("Roles fetched successfully.", data=data)


@sourceRouter.put("/users/roles", response=ApiResponse)
@permissionRequired("roles_update")
def sourceUpdateRole(request, payload: dict):
    role_id = (payload or {}).get("id") or (payload or {}).get("role_id")
    data = AccountsService.updateRole(request.user, role_id, RoleUpdateIn(**{key: value for key, value in (payload or {}).items() if key != "id"}))
    return successResponse("Role updated successfully.", data=data)


@sourceRouter.get("/users/roles/{role_id}/clone", response=ApiResponse)
@permissionRequired("roles_create")
def sourceCloneRole(request, role_id: int):
    role = Role.objects.filter(company_id=request.user.company_id, branch_id=request.user.branch_id, id=role_id, status__in=[0, 1]).first()
    if role is None:
        from apps.common.error_codes import ErrorCodes
        from apps.common.exceptions import api_error

        raise api_error(404, ErrorCodes.NOT_FOUND, "Role not found.")
    payload = RoleIn(
        name=f"{role.name} Copy",
        namespace=f"{role.namespace}-copy",
        description=role.description or "",
        reward_system_id=role.reward_system_id,
        minimal_credit_payment=role.minimal_credit_payment,
        locked=False,
        permission_codenames=list(role.permissions.values_list("codename", flat=True)),
    )
    data = AccountsService.createRole(request.user, payload)
    return successResponse("Role cloned successfully.", data=data)


@sourceRouter.get("/permissions/granted", response=ApiResponse)
def sourceGrantedPermissions(request):
    data = sorted(list(AccountsService.serializeUser(request.user)["permissions"]))
    return successResponse("Granted permissions fetched successfully.", data=data)


@sourceRouter.get("/permissions/{codename}", response=ApiResponse)
def sourceSinglePermission(request, codename: str):
    permissions = AccountsService.buildPermissionDefinitions()
    permission = next((item for item in permissions if item["codename"] == codename), None)
    return successResponse("Permission fetched successfully.", data=permission)
