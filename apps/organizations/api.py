from typing import Optional
from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse, successResponse
from apps.organizations.controllers import OrganizationsController
from apps.organizations.schemas import BranchIn, BranchPatchIn, OrganizationSetupIn
from apps.organizations.services import OrganizationsService
from apps.catalog.schemas import DeleteSchema, StatusUpdateSchema


router = Router(tags=["organizations"])


@router.get("/me", auth=auth_bearer, response=ApiResponse)
def getCurrentOrganization(request):
    """Return the current company and active branch for the signed-in user."""
    return OrganizationsController.getCurrentOrganization(request)


@router.put("/me", auth=auth_bearer, response=ApiResponse)
@permission_required("settings_update", "branches_update")
def updateCurrentOrganization(request, payload: OrganizationSetupIn):
    """Update the placeholder company and Main Branch profile shown after login.

    Example request body:
    {
      "company": {
        "name": "Raj Retail Private Limited",
        "legal_name": "Raj Retail Private Limited",
        "email": "owner@rajretail.com",
        "phone": "9999999999",
        "gst_number": "24ABCDE1234F1Z5",
        "address": "Ring Road, Surat, Gujarat",
        "timezone": "Asia/Kolkata",
        "currency": "INR"
      },
      "branch": {
        "name": "Main Branch",
        "phone": "9999999999",
        "address": "Ground Floor, Ring Road",
        "city": "Surat",
        "state": "Gujarat",
        "country": "India",
        "postal_code": "395002"
      }
    }
    """
    return OrganizationsController.updateCurrentOrganization(
        request,
        payload.company,
        payload.branch,
    )


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
