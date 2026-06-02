import json
from typing import Optional
from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.responses import ApiResponse, successResponse
from apps.organizations.controllers import OrganizationsController
from apps.organizations.schemas import BranchIn, BranchPatchIn, OrganizationSetupIn
from apps.organizations.services import OrganizationsService
from apps.catalog.schemas import DeleteSchema, StatusUpdateSchema


router = Router(tags=["organizations"])


@router.get("/session-data", auth=auth_bearer, response=ApiResponse)
def sessionData(request):
    """Return the current company and active branch for the signed-in user."""
    return OrganizationsController.sessionData(request)


@router.get("/company", auth=auth_bearer, response=ApiResponse)
@permission_required("settings_view")
def getCompany(request):
    """Return company profile data for the company settings page."""
    return OrganizationsController.getCompany(request)


@router.put("/company", auth=auth_bearer, response=ApiResponse)
@permission_required("settings_update")
def updateCompany(request):
    logo = None
    try:
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            raw_payload = request.POST.get("payload")
            if not raw_payload:
                raise ValueError("Missing payload.")
            payload_data = json.loads(raw_payload)
            logo = request.FILES.get("logo")
        else:
            payload_data = json.loads(request.body.decode("utf-8") or "{}")
        payload = OrganizationSetupIn(**payload_data)
    except Exception:
        raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid organization payload.")

    return OrganizationsController.updateCompany(
        request,
        payload.company,
        payload.branch,
        logo,
    )


@router.get("/states/dropdown-list", auth=auth_bearer, response=ApiResponse)
def stateDropdown(request):
    data = OrganizationsService.stateDropdown()
    return successResponse("State dropdown retrieved successfully.", data=data)


@router.post("/branches/", auth=auth_bearer, response=ApiResponse)
@permission_required("branches_create")
def createBranch(request, payload: BranchIn):
    data = OrganizationsService.createBranch(
        request.user,
        payload.dict(exclude_none=True),
        request,
    )
    return successResponse("Branch created successfully.", data=data)


@router.post("/branches/get-transactions", auth=auth_bearer, response=ApiResponse)
@permission_required("branches_view")
def getBranches(request, payload: Optional[dict] = None):
    data = OrganizationsService.listBranches(payload, request)
    return successResponse("Branches retrieved successfully.", data=data)


@router.get("/branches/dropdown-list", auth=auth_bearer, response=ApiResponse)
@permission_required("branches_view")
def branchDropdown(request):
    data = OrganizationsService.branchDropdown(request)
    return successResponse("Dropdown list retrieved successfully.", data=data)


@router.delete("/branches/delete", auth=auth_bearer, response=ApiResponse)
@permission_required("branches_delete")
def deleteBranches(request, payload: DeleteSchema):
    data = OrganizationsService.deleteBranches(payload.dict(), request)
    return successResponse("Branches deleted successfully.", data=data)


@router.patch("/branches/status", auth=auth_bearer, response=ApiResponse)
@permission_required("branches_update")
def updateBranchStatus(request, payload: StatusUpdateSchema):
    data = OrganizationsService.updateBranchStatus(payload.dict(), request)
    return successResponse("Branch status updated successfully.", data=data)


@router.get("/branches/{branch_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("branches_view")
def getBranchById(request, branch_id: int):
    data = OrganizationsService.getBranch(branch_id, request)
    return successResponse("Branch retrieved successfully.", data=data)


@router.put("/branches/{branch_id}", auth=auth_bearer, response=ApiResponse)
@permission_required("branches_update")
def updateBranch(request, branch_id: int, payload: BranchPatchIn):
    data = OrganizationsService.updateBranch(
        request.user,
        branch_id,
        payload.dict(exclude_none=True),
        request,
    )
    return successResponse("Branch updated successfully.", data=data)
