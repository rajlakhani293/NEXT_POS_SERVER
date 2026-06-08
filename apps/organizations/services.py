# type: ignore
from django.db import transaction
from django.utils.text import slugify

from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import saveCompanyLogo, serializeModelInstance
from apps.common.commonQuery import commonQuery
from apps.organizations.models import Branch, Company, StateMaster
from apps.payments.services import PaymentTypeService


class OrganizationsService:
    @staticmethod
    def ensureState(state_id):
        if not state_id:
            return None
        state = StateMaster.objects.filter(id=state_id, status=0).first()
        if state is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "State not found.")
        return state

    @staticmethod
    def generateBranchCode(company_id, name, code=""):
        base_code = slugify(code or name) or "branch"
        branch_code = base_code
        counter = 1
        while Branch.objects.filter(company_id=company_id, code=branch_code).exists():
            counter += 1
            branch_code = f"{base_code}-{counter}"
        return branch_code

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
    def updateCurrentOrganization(user, company_payload, branch_payload=None, logo=None, request=None):
        company = Company.objects.filter(id=user.company_id, status__in=[0, 1]).first()
        branch = None
        if branch_payload is not None:
            branch = Branch.objects.filter(id=user.branch_id, company_id=user.company_id, status__in=[0, 1]).first()
        if company is None or (branch_payload is not None and branch is None):
            raise api_error(
                404,
                ErrorCodes.ORGANIZATION_NOT_FOUND,
                "Organization setup not found.",
            )

        with transaction.atomic():
            company_state = OrganizationsService.ensureState(company_payload.state_id)

            company.name = company_payload.name
            company.legal_name = company_payload.legal_name or company_payload.name
            company.email = company_payload.email or ""
            company.phone = company_payload.phone or ""
            company.gst_number = company_payload.gst_number or ""
            company.city_name = company_payload.city_name or ""
            company.state = company_state
            company.address = company_payload.address or ""
            if logo:
                company.logo = saveCompanyLogo(logo, request) or ""
            else:
                company.logo = company_payload.logo or ""
            company.save()

            if branch_payload is not None:
                branch_state = OrganizationsService.ensureState(branch_payload.state_id)
                branch.name = branch_payload.name
                branch.phone = branch_payload.phone or ""
                branch.address = branch_payload.address or ""
                branch.city = branch_payload.city or ""
                branch.state = branch_state
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

    @staticmethod
    def stateDropdown():
        return list(
            StateMaster.objects.filter(status=0)
            .order_by("name")
            .values("id", "name", "code")
        )

    @staticmethod
    def listBranches(data, request):
        field_config = [["name", True, True], ["code", True, True], ["phone", True, False]]
        result = commonQuery.fetchPaginatedData(
            Branch,
            data,
            field_config,
            {"attributes": ["id", "name", "code", "phone", "city", "state_id", "state__name", "is_head_office", "status"]},
            request=request,
            tenant_config={"company_id": True},
        )
        return result

    @staticmethod
    def branchDropdown(request):
        return commonQuery.findAllRecords(
            Branch,
            {},
            {"attributes": ["id", "name", "code"], "order": ["name"]},
            request=request,
            tenant_config={"company_id": True},
        )

    @staticmethod
    def createBranch(user, data, request):
        with transaction.atomic():
            OrganizationsService.ensureState(data.get("state_id"))
            code = OrganizationsService.generateBranchCode(user.company_id, data.get("name"), data.get("code"))
            branch_data = commonQuery.createRecord(
                Branch,
                {**data, "code": code},
                request=request,
                tenant_config={"company_id": True},
            )
            company = Company.objects.get(id=user.company_id)
            branch = Branch.objects.get(id=branch_data["id"])
            PaymentTypeService.ensureDefaultPaymentTypes(company, branch)
            return branch_data

    @staticmethod
    def getBranch(branch_id, request):
        branch = commonQuery.findOneRecord(
            Branch,
            branch_id,
            request=request,
            tenant_config={"company_id": True},
        )
        if branch is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")
        return branch

    @staticmethod
    def updateBranch(user, branch_id, data, request):
        with transaction.atomic():
            branch = commonQuery.findOneRecord(
                Branch,
                branch_id,
                request=request,
                tenant_config={"company_id": True},
            )
            if branch is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")
            if data.get("code"):
                exists = Branch.objects.filter(company_id=user.company_id, code=slugify(data["code"])).exclude(id=branch_id).exists()
                if exists:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Branch code already exists.")
                data["code"] = slugify(data["code"])
            if data.get("state_id"):
                OrganizationsService.ensureState(data.get("state_id"))
            updated = commonQuery.updateRecordById(
                Branch,
                branch_id,
                data,
                request=request,
                tenant_config={"company_id": True},
            )
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")
            return updated

    @staticmethod
    def deleteBranches(data, request):
        count = commonQuery.softDeleteById(
            Branch,
            data.get("ids"),
            request=request,
            tenant_config={"company_id": True},
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")
        return {"deleted_count": count}

    @staticmethod
    def updateBranchStatus(data, request):
        status = data.get("status")
        if status not in [0, 1]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status must be 0 or 1.")
        count = commonQuery.updateStatusById(
            Branch,
            data.get("ids"),
            status,
            request=request,
            tenant_config={"company_id": True},
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Branch not found.")
        return {"updated_count": count, "status": status}
