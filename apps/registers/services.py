# type: ignore
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode
from apps.common.responses import successResponse
from apps.registers.models import Register


class RegisterService:
    @staticmethod
    def getDefaultRegister(request):
        register = commonQuery.findOneRecord(
            Register,
            {},
            options={"order": ["id"]},
            request=request,
            tenant_config=True,
        )
        if register:
            return register

        return commonQuery.createRecord(
            Register,
            {
                "name": "Main Register",
                "code": buildCode(Register, "Main Register", "main-register", request),
                "location": "Main Branch",
                "description": "Default cash register.",
                "balance": 0,
            },
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def dropdownList(request):
        registers = commonQuery.findAllRecords(
            Register,
            {},
            {"attributes": ["id", "name", "code", "location", "balance"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        if not registers:
            registers = [RegisterService.getDefaultRegister(request)]
        return successResponse("Dropdown list retrieved successfully.", data=registers)

    @staticmethod
    def create(data, request):
        data["code"] = buildCode(Register, data.get("name"), data.get("code"), request)
        register = commonQuery.createRecord(Register, data, request=request, tenant_config=True)
        return successResponse("Cash register created successfully.", data=register)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            Register,
            data,
            [["name", True, True], ["code", True, True], ["location", True, True]],
            {"attributes": ["id", "name", "code", "location", "balance", "status", "created_at"]},
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["is_open"] = item.get("status") == 0
        return successResponse("Cash registers retrieved successfully.", data=result)

    @staticmethod
    def getById(register_id, request):
        register = commonQuery.findOneRecord(Register, register_id, request=request, tenant_config=True)
        if register is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
        register["is_open"] = register.get("status") == 0
        return successResponse("Cash register retrieved successfully.", data=register)

    @staticmethod
    def update(register_id, data, request):
        if data.get("code"):
            data["code"] = buildCode(
                Register,
                data.get("name") or "Cash Register",
                data.get("code"),
                request,
                exclude_id=register_id,
            )
        updated = commonQuery.updateRecordById(Register, register_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
        return successResponse("Cash register updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        count = commonQuery.softDeleteById(Register, data.get("ids"), request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
        return successResponse("Cash registers deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        count = commonQuery.updateStatusById(
            Register,
            data.get("ids"),
            data.get("status"),
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
        return successResponse(
            "Cash register status updated successfully.",
            data={"updated_count": count, "status": data.get("status")},
        )
