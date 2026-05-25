from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.organizations.controllers import OrganizationsController
from apps.organizations.schemas import OrganizationSetupIn


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
