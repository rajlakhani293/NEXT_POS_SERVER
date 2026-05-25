from apps.common.responses import success_response
from apps.organizations.services import OrganizationsService


class OrganizationsController:
    @staticmethod
    def getCurrentOrganization(request):
        data = OrganizationsService.getCurrentOrganization(request.user)
        return success_response("Organization fetched successfully.", data=data)

    @staticmethod
    def updateCurrentOrganization(request, company_payload, branch_payload):
        data = OrganizationsService.updateCurrentOrganization(
            request.user,
            company_payload,
            branch_payload,
        )
        return success_response("Organization updated successfully.", data=data)
