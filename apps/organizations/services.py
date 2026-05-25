from django.db import transaction

from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import serializeModelInstance
from apps.organizations.models import Branch, Company


class OrganizationsService:
    @staticmethod
    def getCurrentOrganization(user):
        company = Company.objects.filter(id=user.company_id, status__in=[0, 1]).first()
        branch = Branch.objects.filter(id=user.branch_id, company_id=user.company_id, status__in=[0, 1]).first()
        if company is None:
            raise api_error(404, ErrorCodes.COMPANY_NOT_FOUND, "Company not found.")

        return {
            "company": serializeModelInstance(company),
            "branch": serializeModelInstance(branch) if branch else None,
        }

    @staticmethod
    def updateCurrentOrganization(user, company_payload, branch_payload):
        company = Company.objects.filter(id=user.company_id, status__in=[0, 1]).first()
        branch = Branch.objects.filter(id=user.branch_id, company_id=user.company_id, status__in=[0, 1]).first()
        if company is None or branch is None:
            raise api_error(
                404,
                ErrorCodes.ORGANIZATION_NOT_FOUND,
                "Organization setup not found.",
            )

        with transaction.atomic():
            company.name = company_payload.name
            company.legal_name = company_payload.legal_name or company_payload.name
            company.email = company_payload.email or ""
            company.phone = company_payload.phone or ""
            company.gst_number = company_payload.gst_number or ""
            company.address = company_payload.address or ""
            company.timezone = company_payload.timezone or "Asia/Kolkata"
            company.currency = company_payload.currency or "INR"
            company.save()

            branch.name = branch_payload.name
            branch.phone = branch_payload.phone or ""
            branch.address = branch_payload.address or ""
            branch.city = branch_payload.city or ""
            branch.state = branch_payload.state or ""
            branch.country = branch_payload.country or "India"
            branch.postal_code = branch_payload.postal_code or ""
            branch.save()

            if getattr(user, "onboarding_completed", False) is False:
                user.onboarding_completed = True
                user.save(update_fields=["onboarding_completed"])

        return {
            "company": serializeModelInstance(company),
            "branch": serializeModelInstance(branch),
            "onboarding_completed": True,
        }
