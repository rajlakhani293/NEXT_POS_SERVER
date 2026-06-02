from apps.common.responses import successResponse
from apps.organizations.services import OrganizationsService


class OrganizationsController:
    @staticmethod
    def sessionData(request):
        data = OrganizationsService.getCurrentOrganization(request.user)
        return successResponse("Organization session data fetched successfully.", data=data)

    @staticmethod
    def getCompany(request):
        data = OrganizationsService.getCurrentOrganization(request.user)
        return successResponse("Company fetched successfully.", data=data)

    @staticmethod
    def updateCompany(request, company_payload, branch_payload=None, logo=None):
        data = OrganizationsService.updateCurrentOrganization(
            request.user,
            company_payload,
            branch_payload,
            logo,
            request,
        )
        return successResponse("Organization updated successfully.", data=data)
