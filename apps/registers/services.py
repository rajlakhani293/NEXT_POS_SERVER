# type: ignore
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounting.services import AccountingService
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode
from apps.common.responses import successResponse
from apps.notifications.services import NotificationService
from apps.registers.models import CashierShift, CashRegister, CashRegisterEntry


def hydrateShift(shift):
    if not shift:
        return None
    data = dict(shift)
    register = CashRegister.objects.filter(id=data.get("register_id")).first()
    cashier = None
    if data.get("cashier_id"):
        from apps.accounts.models import User

        cashier = User.objects.filter(id=data["cashier_id"]).first()
    data["register_name"] = register.name if register else None
    data["cashier_name"] = cashier.full_name if cashier else None
    return data


class RegisterService:
    @staticmethod
    def getDefaultRegister(request):
        register = commonQuery.findOneRecord(
            CashRegister,
            {},
            options={"order": ["id"]},
            request=request,
            tenant_config=True,
        )
        if register:
            return register

        return commonQuery.createRecord(
            CashRegister,
            {
                "name": "Main Register",
                "code": buildCode(CashRegister, "Main Register", "main-register", request),
                "location": "Main Branch",
            },
            request=request,
            tenant_config=True,
        )

    @staticmethod
    def dropdownList(request):
        registers = commonQuery.findAllRecords(
            CashRegister,
            {},
            {"attributes": ["id", "name", "code"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        if not registers:
            registers = [RegisterService.getDefaultRegister(request)]
        return successResponse("Dropdown list retrieved successfully.", data=registers)


class CashierShiftService:
    @staticmethod
    def current(request):
        shift = commonQuery.findOneRecord(
            CashierShift,
            {"cashier_id": request.user.id, "shift_status": "open"},
            request=request,
            tenant_config=True,
        )
        return successResponse(
            "Current shift retrieved successfully.",
            data=hydrateShift(shift),
        )

    @staticmethod
    def open(data, request):
        with transaction.atomic():
            current = commonQuery.findOneRecord(
                CashierShift,
                {"cashier_id": request.user.id, "shift_status": "open"},
                request=request,
                tenant_config=True,
            )
            if current:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "You already have an open shift.")

            register = None
            if data.get("register_id"):
                register = commonQuery.findOneRecord(
                    CashRegister,
                    data["register_id"],
                    request=request,
                    tenant_config=True,
                )
                if register is None:
                    raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
            else:
                register = RegisterService.getDefaultRegister(request)

            opening_cash = data.get("opening_cash") or 0
            shift = commonQuery.createRecord(
                CashierShift,
                {
                    "register_id": register["id"],
                    "cashier_id": request.user.id,
                    "opened_by_id": request.user.id,
                    "shift_status": "open",
                    "opened_at": timezone.now(),
                    "opening_cash": opening_cash,
                    "expected_cash": opening_cash,
                    "note": data.get("note") or "",
                },
                request=request,
                tenant_config=True,
            )
            commonQuery.createRecord(
                CashRegisterEntry,
                {
                    "shift_id": shift["id"],
                    "register_id": register["id"],
                    "cashier_id": request.user.id,
                    "entry_type": "opening",
                    "amount": opening_cash,
                    "balance_before": 0,
                    "balance_after": opening_cash,
                    "note": "Opening cash",
                },
                request=request,
                tenant_config=True,
            )
            if Decimal(str(opening_cash or 0)) > 0:
                AccountingService.record(
                    account_code="cash",
                    name="Opening cash",
                    transaction_type="adjustment",
                    action_type="credit",
                    amount=opening_cash,
                    source_type="cash_register",
                    source_id=shift["id"],
                    description=data.get("note") or "Opening cash",
                    request=request,
                )
            return successResponse("Shift opened successfully.", data=hydrateShift(shift))

    @staticmethod
    def close(data, request):
        with transaction.atomic():
            shift_id = data.get("shift_id")
            where = {"id": shift_id} if shift_id else {"cashier_id": request.user.id, "shift_status": "open"}
            shift = commonQuery.findOneRecord(
                CashierShift,
                where,
                request=request,
                tenant_config=True,
            )
            if shift is None or shift.get("shift_status") != "open":
                raise api_error(404, ErrorCodes.NOT_FOUND, "Open shift not found.")

            declared_cash = Decimal(str(data.get("declared_cash") or 0))
            expected_cash = Decimal(str(shift.get("expected_cash") or 0))
            difference_amount = declared_cash - expected_cash
            closed = commonQuery.updateRecordById(
                CashierShift,
                shift["id"],
                {
                    "closed_by_id": request.user.id,
                    "shift_status": "closed",
                    "closed_at": timezone.now(),
                    "declared_cash": declared_cash,
                    "difference_amount": difference_amount,
                    "note": data.get("note") or shift.get("note") or "",
                },
                request=request,
                tenant_config=True,
            )
            commonQuery.createRecord(
                CashRegisterEntry,
                {
                    "shift_id": shift["id"],
                    "register_id": shift["register_id"],
                    "cashier_id": request.user.id,
                    "entry_type": "closing",
                    "amount": declared_cash,
                    "balance_before": expected_cash,
                    "balance_after": declared_cash,
                    "note": data.get("note") or "Closing cash",
                },
                request=request,
                tenant_config=True,
            )
            return successResponse("Shift closed successfully.", data=hydrateShift(closed))

    @staticmethod
    def getAll(data, request):
        fieldConfig = [
            ["shift_status", True, True],
            ["opened_at", False, True],
            ["closed_at", False, True],
        ]
        options = {
            "attributes": [
                "id",
                "register_id",
                "cashier_id",
                "shift_status",
                "opened_at",
                "closed_at",
                "opening_cash",
                "expected_cash",
                "declared_cash",
                "difference_amount",
                "total_sales_amount",
                "status",
            ],
        }
        result = commonQuery.fetchPaginatedData(
            CashierShift,
            data,
            fieldConfig,
            options,
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            hydrated = hydrateShift(item)
            item.update(hydrated or {})
        return successResponse("Shifts retrieved successfully.", data=result)

    @staticmethod
    def cashMovement(data, request, movement_type):
        if movement_type not in ["cash_in", "cash_out"]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid cash movement.")
        amount = Decimal(str(data.get("amount") or 0))
        if amount <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Amount must be greater than 0.")

        with transaction.atomic():
            where = {"id": data.get("shift_id")} if data.get("shift_id") else {"cashier_id": request.user.id, "shift_status": "open"}
            shift = commonQuery.findOneRecord(CashierShift, where, request=request, tenant_config=True)
            if shift is None or shift.get("shift_status") != "open":
                raise api_error(404, ErrorCodes.NOT_FOUND, "Open shift not found.")

            balance_before = Decimal(str(shift.get("expected_cash") or 0))
            balance_after = balance_before + amount if movement_type == "cash_in" else balance_before - amount
            shift_updates = {"expected_cash": balance_after}
            if movement_type == "cash_in":
                shift_updates["total_cash_in"] = Decimal(str(shift.get("total_cash_in") or 0)) + amount
            else:
                shift_updates["total_cash_out"] = Decimal(str(shift.get("total_cash_out") or 0)) + amount

            updated = commonQuery.updateRecordById(
                CashierShift,
                shift["id"],
                shift_updates,
                request=request,
                tenant_config=True,
            )
            entry = commonQuery.createRecord(
                CashRegisterEntry,
                {
                    "shift_id": shift["id"],
                    "register_id": shift["register_id"],
                    "cashier_id": request.user.id,
                    "entry_type": movement_type,
                    "amount": amount,
                    "balance_before": balance_before,
                    "balance_after": balance_after,
                    "note": data.get("note") or movement_type.replace("_", " ").title(),
                },
                request=request,
                tenant_config=True,
            )
            AccountingService.record(
                account_code="cash",
                name=movement_type.replace("_", " ").title(),
                transaction_type="adjustment",
                action_type="credit" if movement_type == "cash_in" else "debit",
                amount=amount,
                source_type="cash_register",
                source_id=entry["id"],
                description=data.get("note") or movement_type.replace("_", " ").title(),
                request=request,
            )
            NotificationService.push(
                title=movement_type.replace("_", " ").title(),
                message=f"Cash movement of {amount} recorded.",
                notification_type="info",
                source_type="cash_register",
                source_id=entry["id"],
                action_url="/registers",
                request=request,
            )
            updated["entry"] = entry
            return successResponse(f"{movement_type.replace('_', ' ').title()} recorded successfully.", data=hydrateShift(updated))
