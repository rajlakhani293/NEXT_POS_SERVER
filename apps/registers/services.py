# type: ignore
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
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
    def ensureDefaultRegister(company, branch):
        register, _created = CashRegister.objects.get_or_create(
            company_id=company.id,
            branch_id=branch.id,
            code="main-register",
            defaults={
                "name": "Main Register",
                "location": "Main Branch",
            },
        )
        return register

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
            {"attributes": ["id", "name", "code", "location"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        if not registers:
            registers = [RegisterService.getDefaultRegister(request)]
        return successResponse("Dropdown list retrieved successfully.", data=registers)

    @staticmethod
    def create(data, request):
        data["code"] = buildCode(CashRegister, data.get("name"), data.get("code"), request)
        register = commonQuery.createRecord(CashRegister, data, request=request, tenant_config=True)
        return successResponse("Cash register created successfully.", data=register)

    @staticmethod
    def getAll(data, request):
        result = commonQuery.fetchPaginatedData(
            CashRegister,
            data,
            [["name", True, True], ["code", True, True], ["location", True, True]],
            {"attributes": ["id", "name", "code", "location", "status", "created_at"]},
            request=request,
            tenant_config=True,
        )
        open_register_ids = set(
            CashierShift.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                shift_status="open",
                status__in=[0, 1],
            ).values_list("register_id", flat=True)
        )
        for item in result["items"]:
            item["is_open"] = item["id"] in open_register_ids
        return successResponse("Cash registers retrieved successfully.", data=result)

    @staticmethod
    def getById(register_id, request):
        register = commonQuery.findOneRecord(CashRegister, register_id, request=request, tenant_config=True)
        if register is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
        register["is_open"] = CashierShift.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            register_id=register_id,
            shift_status="open",
            status__in=[0, 1],
        ).exists()
        return successResponse("Cash register retrieved successfully.", data=register)

    @staticmethod
    def update(register_id, data, request):
        if data.get("code"):
            data["code"] = buildCode(
                CashRegister,
                data.get("name") or "Cash Register",
                data.get("code"),
                request,
                exclude_id=register_id,
            )
        updated = commonQuery.updateRecordById(CashRegister, register_id, data, request=request, tenant_config=True)
        if updated is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
        return successResponse("Cash register updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        ids = data.get("ids")
        register_ids = ids if isinstance(ids, list) else [ids]
        if CashierShift.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            register_id__in=register_ids,
            shift_status="open",
            status__in=[0, 1],
        ).exists():
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Cannot delete a cash register that is currently open.")
        count = commonQuery.softDeleteById(CashRegister, ids, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
        return successResponse("Cash registers deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        ids = data.get("ids")
        register_ids = ids if isinstance(ids, list) else [ids]
        if status == 1 and CashierShift.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            register_id__in=register_ids,
            shift_status="open",
            status__in=[0, 1],
        ).exists():
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Cannot deactivate a cash register that is currently open.")
        count = commonQuery.updateStatusById(CashRegister, ids, status, request=request, tenant_config=True)
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Cash register not found.")
        return successResponse("Cash register status updated successfully.", data={"updated_count": count, "status": status})


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

            if register.get("status") != 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Cash register is not active.")

            register_in_use = commonQuery.findOneRecord(
                CashierShift,
                {"register_id": register["id"], "shift_status": "open"},
                request=request,
                tenant_config=True,
            )
            if register_in_use:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Cash register is already open.")

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

        register_id = ((data or {}).get("filter") or {}).get("register_id")
        if register_id:
            result["register"] = commonQuery.findOneRecord(
                CashRegister,
                register_id,
                options={"attributes": ["id", "name", "location"]},
                request=request,
                tenant_config=True,
            )
        return successResponse("Shifts retrieved successfully.", data=result)

    @staticmethod
    def getById(shift_id, request):
        shift = commonQuery.findOneRecord(
            CashierShift,
            shift_id,
            request=request,
            tenant_config=True,
        )
        if shift is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Shift not found.")

        entries_queryset = CashRegisterEntry.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            shift_id=shift_id,
            status__in=[0, 1],
        )
        entries = list(
            entries_queryset.values(
                "id",
                "entry_type",
                "payment_type",
                "amount",
                "balance_before",
                "balance_after",
                "reference_type",
                "reference_id",
                "note",
                "created_at",
            ).order_by("-created_at", "-id")
        )
        data = hydrateShift(shift)
        data["entries"] = entries
        data["entry_count"] = len(entries)
        data["z_report"] = {
            "opening_cash": shift.get("opening_cash") or 0,
            "expected_cash": shift.get("expected_cash") or 0,
            "declared_cash": shift.get("declared_cash") or 0,
            "difference_amount": shift.get("difference_amount") or 0,
            "sales_collected": shift.get("total_sales_amount") or 0,
            "refund_out": shift.get("total_refund_amount") or 0,
            "cash_in": shift.get("total_cash_in") or 0,
            "cash_out": shift.get("total_cash_out") or 0,
            "entry_count": len(entries),
            "totals_by_type": list(
                entries_queryset.values("entry_type")
                .annotate(total=Sum("amount"))
                .order_by("entry_type")
            ),
        }
        return successResponse("Shift retrieved successfully.", data=data)

    @staticmethod
    def getEntries(shift_id, data, request):
        shift = commonQuery.findOneRecord(
            CashierShift,
            shift_id,
            request=request,
            tenant_config=True,
        )
        if shift is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Shift not found.")

        result = commonQuery.fetchPaginatedData(
            CashRegisterEntry,
            {
                **(data or {}),
                "filter": {
                    **((data or {}).get("filter") or {}),
                    "shift_id": shift_id,
                },
            },
            [["entry_type", True, True], ["payment_type", True, True], ["note", True, True]],
            {
                "attributes": [
                    "id",
                    "entry_type",
                    "payment_type",
                    "amount",
                    "balance_before",
                    "balance_after",
                    "reference_type",
                    "reference_id",
                    "note",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Shift entries retrieved successfully.", data=result)

    @staticmethod
    def getZReport(shift_id, request):
        shift = commonQuery.findOneRecord(
            CashierShift,
            shift_id,
            request=request,
            tenant_config=True,
        )
        if shift is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Shift not found.")

        entries = CashRegisterEntry.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            shift_id=shift_id,
            status__in=[0, 1],
        )
        data = hydrateShift(shift)
        data["z_report"] = {
            "opening_cash": shift.get("opening_cash") or 0,
            "expected_cash": shift.get("expected_cash") or 0,
            "declared_cash": shift.get("declared_cash") or 0,
            "difference_amount": shift.get("difference_amount") or 0,
            "sales_collected": shift.get("total_sales_amount") or 0,
            "refund_out": shift.get("total_refund_amount") or 0,
            "cash_in": shift.get("total_cash_in") or 0,
            "cash_out": shift.get("total_cash_out") or 0,
            "entry_count": entries.count(),
            "totals_by_type": list(
                entries.values("entry_type").annotate(total=Sum("amount")).order_by("entry_type")
            ),
        }
        return successResponse("Z report retrieved successfully.", data=data)

    @staticmethod
    def refresh(shift_id, request):
        shift = commonQuery.findOneRecord(CashierShift, shift_id, request=request, tenant_config=True)
        if shift is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Shift not found.")

        entries = CashRegisterEntry.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            shift_id=shift_id,
            status__in=[0, 1],
        )
        opening = entries.filter(entry_type="opening").aggregate(total=Sum("amount")).get("total") or Decimal("0")
        sale_payments = entries.filter(entry_type="sale_payment").aggregate(total=Sum("amount")).get("total") or Decimal("0")
        cash_in = entries.filter(entry_type="cash_in").aggregate(total=Sum("amount")).get("total") or Decimal("0")
        refunds = entries.filter(entry_type="refund").aggregate(total=Sum("amount")).get("total") or Decimal("0")
        cash_out = entries.filter(entry_type__in=["cash_out", "expense", "change_given"]).aggregate(total=Sum("amount")).get("total") or Decimal("0")
        expected_cash = opening + sale_payments + cash_in - refunds - cash_out
        updated = commonQuery.updateRecordById(
            CashierShift,
            shift_id,
            {
                "opening_cash": opening,
                "expected_cash": expected_cash,
                "total_sales_amount": sale_payments,
                "total_refund_amount": refunds,
                "total_cash_in": cash_in,
                "total_cash_out": cash_out,
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Shift refreshed successfully.", data=hydrateShift(updated))

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
            if movement_type == "cash_out" and balance_after < 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Not enough cash in register.")
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
