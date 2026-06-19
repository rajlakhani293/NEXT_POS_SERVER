# type: ignore
from django.db import transaction

from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import decimalValue as money
from apps.common.responses import successResponse
from apps.registers.models import Register, RegistersHistory


class RegisterService:
    @staticmethod
    def _getRegister(register_id, request, for_update=False):
        queryset = Register.objects
        if for_update:
            queryset = queryset.select_for_update()
        register = (
            queryset.filter(
                id=register_id,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
            )
            .exclude(status=2)
            .first()
        )
        if register is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
        return register

    @staticmethod
    def _serialize(register):
        return {
            "id": register.id,
            "name": register.name,
            "description": register.description,
            "used_by_id": register.used_by_id,
            "balance": register.balance,
            "register_status": register.register_status,
            "is_open": register.register_status in [Register.STATUS_OPENED, Register.STATUS_INUSE],
            "status": register.status,
            "created_at": register.created_at,
            "updated_at": register.updated_at,
        }

    @staticmethod
    def recordHistory(register_id, action, amount, request, note=None, payment_id=None, payment_type_id=0, order_id=None):
        amount = money(amount)
        with transaction.atomic():
            register = RegisterService._getRegister(register_id, request, for_update=True)
            balance_before = money(register.balance)
            if action in RegistersHistory.IN_ACTIONS:
                balance_after = balance_before + amount
                transaction_type = "positive" if amount > 0 else "unchanged"
            elif action in RegistersHistory.OUT_ACTIONS:
                balance_after = balance_before - amount
                transaction_type = "negative" if amount > 0 else "unchanged"
            else:
                balance_after = balance_before
                transaction_type = "unchanged"

            history = commonQuery.createRecord(
                RegistersHistory,
                {
                    "register_id": register.id,
                    "payment_id": payment_id,
                    "payment_type_id": payment_type_id or 0,
                    "order_id": order_id,
                    "entry_type": action,
                    "amount": amount,
                    "note": note,
                    "balance_before": balance_before,
                    "balance_after": balance_after,
                    "transaction_type": transaction_type,
                },
                request=request,
                tenant_config=True,
            )
            register.balance = balance_after
            register.save(update_fields=["balance", "updated_at"])
            history["register_balance"] = balance_after
            return history

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
            {"attributes": ["id", "name", "description", "balance", "register_status"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        if not registers:
            registers = [RegisterService.getDefaultRegister(request)]
        return successResponse("Dropdown list retrieved successfully.", data=registers)

    @staticmethod
    def create(data, request):
        register = commonQuery.createRecord(Register, data, request=request, tenant_config=True)
        return successResponse("Cash register created successfully.", data=register)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            Register,
            data,
            [["name", True, True], ["description", True, True]],
            {"attributes": ["id", "name", "description", "balance", "register_status", "status", "created_at"]},
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["is_open"] = item.get("register_status") in [Register.STATUS_OPENED, Register.STATUS_INUSE]
        return successResponse("Cash registers retrieved successfully.", data=result)

    @staticmethod
    def getById(register_id, request):
        register = commonQuery.findOneRecord(Register, register_id, request=request, tenant_config=True)
        if register is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
        register["is_open"] = register.get("register_status") in [Register.STATUS_OPENED, Register.STATUS_INUSE]
        return successResponse("Cash register retrieved successfully.", data=register)

    @staticmethod
    def update(register_id, data, request):
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

    @staticmethod
    def openRegister(data, request):
        with transaction.atomic():
            register = RegisterService._getRegister(data.get("register_id"), request, for_update=True)
            if register.register_status in [Register.STATUS_OPENED, Register.STATUS_INUSE]:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Cash register is already open.")
            register.register_status = Register.STATUS_OPENED
            register.used_by = request.user
            register.save(update_fields=["register_status", "used_by", "updated_at"])
            history = RegisterService.recordHistory(
                data.get("register_id"),
                RegistersHistory.ACTION_OPENING,
                data.get("amount"),
                request,
                data.get("note") or "Register opening",
            )
        return successResponse("Cash register opened successfully.", data=history)

    @staticmethod
    def closeRegister(data, request):
        with transaction.atomic():
            register = RegisterService._getRegister(data.get("register_id"), request, for_update=True)
            if register.register_status not in [Register.STATUS_OPENED, Register.STATUS_INUSE]:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Cash register is not open.")
            history = RegisterService.recordHistory(
                data.get("register_id"),
                RegistersHistory.ACTION_CLOSING,
                data.get("amount"),
                request,
                data.get("note") or "Register closing",
            )
            Register.objects.filter(id=register.id).update(register_status=Register.STATUS_CLOSED, used_by=None)
        return successResponse("Cash register closed successfully.", data=history)

    @staticmethod
    def cashIn(data, request):
        history = RegisterService.recordHistory(
            data.get("register_id"),
            RegistersHistory.ACTION_CASHING,
            data.get("amount"),
            request,
            data.get("note") or "Cash in",
        )
        return successResponse("Cash added successfully.", data=history)

    @staticmethod
    def cashOut(data, request):
        history = RegisterService.recordHistory(
            data.get("register_id"),
            RegistersHistory.ACTION_CASHOUT,
            data.get("amount"),
            request,
            data.get("note") or "Cash out",
        )
        return successResponse("Cash removed successfully.", data=history)
