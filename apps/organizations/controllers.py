from apps.common.responses import successResponse
from apps.organizations.services import OrganizationsService


class OrganizationsController:
    @staticmethod
    def getCurrentOrganization(request):
        data = OrganizationsService.getCurrentOrganization(request.user)
        return successResponse("Organization fetched successfully.", data=data)

    @staticmethod
    def updateCurrentOrganization(request, company_payload, branch_payload):
        data = OrganizationsService.updateCurrentOrganization(
            request.user,
            company_payload,
            branch_payload,
        )
        return successResponse("Organization updated successfully.", data=data)
