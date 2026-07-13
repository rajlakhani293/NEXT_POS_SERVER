# type: ignore
from django.db import transaction
from django.utils.text import slugify

from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import saveCompanyLogo, serializeModelInstance, validateUniqueFields
from apps.common.commonQuery import commonQuery
from apps.common.tenantDefaults import TenantDefaultsService
from apps.organizations.models import Branch, Company


class OrganizationsService:
    @staticmethod
    def generateBranchCode(company_id, name, code=""):
        base_code = slugify(code or name) or "branch"
        branch_code = base_code
        counter = 1
        while commonQuery.existsRecord(
            Branch,
            {"company_id": company_id, "code": branch_code},
            tenant_config={},
        ):
            counter += 1
            branch_code = f"{base_code}-{counter}"
        return branch_code

    @staticmethod
    def getCurrentOrganization(user):
        company = commonQuery.findOneRecord(
            Company,
            {"id": user.company_id, "status__in": [0, 1]},
            tenant_config={},
        )
        branch = commonQuery.findOneRecord(
            Branch,
            {"id": user.branch_id, "company_id": user.company_id, "status__in": [0, 1]},
            tenant_config={},
        )
        if company is None:
            raise api_error(404, ErrorCodes.COMPANY_NOT_FOUND, "Company not found.")

        return {
            "company": company,
            "branch": branch,
        }

    @staticmethod
    def updateCurrentOrganization(user, company_payload, branch_payload=None, logo=None, request=None):
        company = commonQuery.findOneInstance(
            Company,
            {"id": user.company_id, "status__in": [0, 1]},
            tenant_config={},
        )
        branch = None
        if branch_payload is not None:
            branch = commonQuery.findOneInstance(
                Branch,
                {"id": user.branch_id, "company_id": user.company_id, "status__in": [0, 1]},
                tenant_config={},
            )
        if company is None or (branch_payload is not None and branch is None):
            raise api_error(
                404,
                ErrorCodes.ORGANIZATION_NOT_FOUND,
                "Organization setup not found.",
            )

        with transaction.atomic():
            validateUniqueFields(
                Company,
                {"name": company_payload.name},
                request=request,
                scope="global",
                exclude_id=company.id,
                case_insensitive=["name"],
                status_in=(0, 1),
            )
            if branch_payload is not None:
                validateUniqueFields(
                    Branch,
                    {"name": branch_payload.name},
                    request=request,
                    scope="company",
                    exclude_id=branch.id,
                    case_insensitive=["name"],
                    status_in=(0, 1),
                )
            company.name = company_payload.name
            company.legal_name = company_payload.legal_name or company_payload.name
            company.email = company_payload.email or ""
            company.phone = company_payload.phone or ""
            company.gst_number = company_payload.gst_number or ""
            company.city_name = company_payload.city_name or ""
            company.state = company_payload.state or ""
            company.address = company_payload.address or ""
            if logo:
                company.logo = saveCompanyLogo(logo, request) or ""
            else:
                company.logo = company_payload.logo or ""
            company.save()

            if branch_payload is not None:
                branch.name = branch_payload.name
                branch.phone = branch_payload.phone or ""
                branch.address = branch_payload.address or ""
                branch.city = branch_payload.city or ""
                branch.state = branch_payload.state or ""
                branch.postal_code = branch_payload.postal_code or ""
                branch.save()

        return {
            "company": serializeModelInstance(company),
            "branch": serializeModelInstance(branch),
        }

    @staticmethod
    def listBranches(data, request):
        field_config = [["name", True, True], ["code", True, True], ["phone", True, False]]
        result = commonQuery.fetchPaginatedData(
            Branch,
            data,
            field_config,
            {"attributes": ["id", "name", "code", "phone", "city", "state", "is_head_office", "status"]},
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
            code = OrganizationsService.generateBranchCode(user.company_id, data.get("name"), data.get("code"))
            branch_data = commonQuery.createRecord(
                Branch,
                {**data, "code": code},
                request=request,
                tenant_config={"company_id": True},
            )
            company = commonQuery.findOneInstance(Company, user.company_id, tenant_config={})
            branch = commonQuery.findOneInstance(Branch, branch_data["id"], tenant_config={})
            TenantDefaultsService.ensureBranchDefaults(company, branch)
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
                data["code"] = slugify(data["code"])
                validateUniqueFields(
                    Branch,
                    {"code": data["code"]},
                    request=request,
                    scope="company",
                    exclude_id=branch_id,
                    status_in=None,
                    messages={"code": "Branch code already exists."},
                )
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
