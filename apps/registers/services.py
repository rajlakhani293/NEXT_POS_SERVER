# type: ignore
from django.db import transaction
from django.db.models import Sum
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import decimalValue as money
from apps.common.responses import successResponse
from apps.registers.models import Register, RegistersHistory
from apps.settings.models import PaymentType
from apps.settings.services import OptionSettingService


class RegisterService:
    @staticmethod
    def requestFromJob(job):
        from apps.common.helpers import requestFromJobUser

        return requestFromJobUser(job)

    @staticmethod
    def _getRegister(register_id, request, for_update=False):
        queryset = commonQuery.branchScopedQueryset(Register, {"id": register_id}, request)
        if for_update:
            queryset = queryset.select_for_update()
        register = (
            queryset
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
            if action in [RegistersHistory.ACTION_CASHING, RegistersHistory.ACTION_CASHOUT] and amount <= 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Amount must be greater than 0.")
            if action in [RegistersHistory.ACTION_CASHING, RegistersHistory.ACTION_CASHOUT] and register.register_status not in [Register.STATUS_OPENED, Register.STATUS_INUSE]:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Cash register must be open.")
            if action == RegistersHistory.ACTION_CASHOUT and balance_before - amount < 0:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Not enough fund to cash out.")
            if action == RegistersHistory.ACTION_CLOSING:
                balance_after = balance_before - amount
                if balance_before == amount:
                    transaction_type = "unchanged"
                elif balance_before < amount:
                    transaction_type = "positive"
                else:
                    transaction_type = "negative"
            elif action in RegistersHistory.IN_ACTIONS:
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
    def resolvePaymentTypeId(identifier, request):
        if not identifier:
            return 0
        payment_type = (
            commonQuery.branchScopedQueryset(
                PaymentType,
                {"identifier": identifier, "status__in": [0, 1]},
                request,
            )
            .values("id")
            .first()
        )
        return payment_type["id"] if payment_type else 0

    @staticmethod
    def defaultChangePaymentTypeId(request):
        configured = OptionSettingService.getOptionValue(
            request.user.company,
            request.user.branch,
            "registers_default_change_payment_type",
            None,
        )
        if isinstance(configured, int):
            return configured
        return RegisterService.resolvePaymentTypeId(configured or "cash-payment", request)

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
            {"attributes": ["id", "name", "description", "balance", "register_status", "status", "created_at", "user__username", "used_by__username"]},
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["is_open"] = item.get("register_status") in [Register.STATUS_OPENED, Register.STATUS_INUSE]
            item["user_username"] = item.pop("user__username", None)
            item["cashier_username"] = item.pop("used_by__username", None)
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
            commonQuery.branchScopedQueryset(Register, {"id": register.id}, request).update(
                register_status=Register.STATUS_CLOSED,
                used_by=None,
                balance=0,
            )
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

    @staticmethod
    def refreshCashRegister(register_id, request):
        register = RegisterService._getRegister(register_id, request, for_update=True)
        if register.register_status == Register.STATUS_CLOSED:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to refresh a closed cash register.")

        last_opening = (
            commonQuery.branchScopedQueryset(
                RegistersHistory,
                {"register_id": register.id, "entry_type": RegistersHistory.ACTION_OPENING},
                request,
            )
            .exclude(status=2)
            .order_by("-id")
            .first()
        )
        if last_opening is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Register opening history not found.")

        base_queryset = commonQuery.branchScopedQueryset(
            RegistersHistory,
            {"register_id": register.id, "created_at__gte": last_opening.created_at},
            request,
        ).exclude(status=2)
        total_in = base_queryset.filter(entry_type__in=RegistersHistory.IN_ACTIONS).aggregate(total=Sum("amount"))["total"] or 0
        total_out = base_queryset.filter(entry_type__in=RegistersHistory.OUT_ACTIONS).aggregate(total=Sum("amount"))["total"] or 0
        register.balance = money(total_in) - money(total_out)
        register.save(update_fields=["balance", "updated_at"])
        return successResponse("Cash register refreshed successfully.", data=RegisterService._serialize(register))

    @staticmethod
    def recordOrderPayment(payment_id, request):
        from apps.sales.models import OrderPayment

        payment = (
            commonQuery.branchScopedQueryset(OrderPayment, {"id": payment_id}, request)
            .select_related("sale_order")
            .exclude(status=2)
            .first()
        )
        if payment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Order payment not found.")
        if payment.sale_order.register_id is None:
            return successResponse("Order payment has no cash register to track.", data=None)

        existing = commonQuery.findOneRecord(
            RegistersHistory,
            {"payment_id": payment.id, "entry_type": RegistersHistory.ACTION_ORDER_PAYMENT},
            request=request,
            tenant_config=True,
        )
        if existing:
            return successResponse("Cash register payment already recorded.", data=existing)

        history = RegisterService.recordHistory(
            payment.sale_order.register_id,
            RegistersHistory.ACTION_ORDER_PAYMENT,
            payment.value,
            request,
            "Order payment",
            payment_id=payment.id,
            payment_type_id=RegisterService.resolvePaymentTypeId(payment.identifier, request),
            order_id=payment.sale_order_id,
        )
        return successResponse("Cash register payment recorded successfully.", data=history)

    @staticmethod
    def recordOrderChange(order_id, request):
        from apps.sales.models import Order

        sale_order = (
            commonQuery.branchScopedQueryset(Order, {"id": order_id}, request)
            .exclude(status=2)
            .first()
        )
        if sale_order is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Order not found.")
        if sale_order.payment_status != "paid" or money(sale_order.change_amount) <= 0 or sale_order.register_id is None:
            return successResponse("Order has no cash change to track.", data=None)

        existing = commonQuery.findOneRecord(
            RegistersHistory,
            {"order_id": sale_order.id, "entry_type": RegistersHistory.ACTION_ORDER_CHANGE},
            request=request,
            tenant_config=True,
        )
        if existing:
            return successResponse("Cash register change already recorded.", data=existing)

        history = RegisterService.recordHistory(
            sale_order.register_id,
            RegistersHistory.ACTION_ORDER_CHANGE,
            sale_order.change_amount,
            request,
            "Change on cash",
            payment_type_id=RegisterService.defaultChangePaymentTypeId(request),
            order_id=sale_order.id,
        )
        return successResponse("Cash register change recorded successfully.", data=history)

    @staticmethod
    def deleteRegisterHistoryUsingOrder(order_id, request):
        histories = commonQuery.branchScopedQueryset(RegistersHistory, {"order_id": order_id}, request).exclude(status=2)
        register_ids = list(histories.values_list("register_id", flat=True).distinct())
        deleted_count = histories.delete()[0]
        for register_id in register_ids:
            register = commonQuery.branchScopedQueryset(Register, {"id": register_id}, request).first()
            if register and register.register_status != Register.STATUS_CLOSED:
                RegisterService.refreshCashRegister(register_id, request)
        return successResponse("Register history deleted successfully.", data={"deleted_count": deleted_count})

    @staticmethod
    def jobHandlers():
        return {
            "track_cash_register_payment": lambda data, job: RegisterService.recordOrderPayment(
                data.get("payment_id") or data.get("order_payment_id"),
                RegisterService.requestFromJob(job),
            ),
            "record_order_change": lambda data, job: RegisterService.recordOrderChange(
                data.get("order_id") or data.get("sale_order_id"),
                RegisterService.requestFromJob(job),
            ),
            "refresh_cash_register": lambda data, job: RegisterService.refreshCashRegister(
                data.get("register_id"),
                RegisterService.requestFromJob(job),
            ),
            "delete_register_history_using_order": lambda data, job: RegisterService.deleteRegisterHistoryUsingOrder(
                data.get("order_id") or data.get("sale_order_id"),
                RegisterService.requestFromJob(job),
            ),
        }

    @staticmethod
    def getCurrentShift(request):
        register = commonQuery.findOneInstance(
            Register,
            {"used_by_id": request.user.id, "register_status": Register.STATUS_OPENED},
            request=request,
            tenant_config=True,
        )
        if not register:
            return successResponse("No active register shift found.", data=None)

        last_opening = (
            commonQuery.branchScopedQueryset(
                RegistersHistory,
                {"register_id": register.id, "entry_type": RegistersHistory.ACTION_OPENING},
                request,
            )
            .exclude(status=2)
            .order_by("-id")
            .first()
        )
        opened_at = last_opening.created_at if last_opening else register.created_at
        opening_cash = last_opening.amount if last_opening else 0

        return successResponse(
            "Current active shift retrieved.",
            data={
                "id": register.id,
                "register_id": register.id,
                "register_name": register.name,
                "cashier_name": request.user.full_name or request.user.username,
                "shift_status": "active",
                "opened_at": opened_at,
                "opening_cash": float(opening_cash),
                "expected_cash": float(register.balance),
                "declared_cash": None,
                "difference_amount": 0,
            },
        )

    @staticmethod
    def getShiftsData(data, request):
        register_id = (data or {}).get("filter", {}).get("register_id")
        if not register_id:
            register_id = (data or {}).get("register_id")
        if not register_id:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "register_id is required.")

        openings_qs = commonQuery.branchScopedQueryset(
            RegistersHistory,
            {"register_id": register_id, "entry_type": RegistersHistory.ACTION_OPENING},
            request,
        ).exclude(status=2).order_by("-created_at")

        page = max(int((data or {}).get("page", 1)), 1)
        limit = int((data or {}).get("limit", 10))
        offset = (page - 1) * limit

        total_shifts = openings_qs.count()
        paginated_openings = openings_qs[offset : offset + limit]

        shifts = []
        for opening in paginated_openings:
            closing = (
                commonQuery.branchScopedQueryset(
                    RegistersHistory,
                    {
                        "register_id": register_id,
                        "entry_type": RegistersHistory.ACTION_CLOSING,
                        "created_at__gt": opening.created_at,
                    },
                    request,
                )
                .exclude(status=2)
                .order_by("created_at")
                .first()
            )

            if closing:
                status = "closed"
                closed_at = closing.created_at
                declared_cash = closing.amount
                expected_cash = closing.balance_before
                difference_amount = closing.amount - closing.balance_before
            else:
                status = "active"
                closed_at = None
                declared_cash = None
                reg = commonQuery.branchScopedQueryset(Register, {"id": register_id}, request).first()
                expected_cash = reg.balance if reg else 0
                difference_amount = 0

            shifts.append(
                {
                    "id": opening.id,
                    "cashier_name": opening.user.full_name or opening.user.username if opening.user else "System",
                    "shift_status": status,
                    "opened_at": opening.created_at,
                    "closed_at": closed_at,
                    "opening_cash": float(opening.amount),
                    "expected_cash": float(expected_cash),
                    "declared_cash": float(declared_cash) if declared_cash is not None else None,
                    "difference_amount": float(difference_amount),
                }
            )

        return successResponse(
            "Register shifts retrieved successfully.",
            data={
                "items": shifts,
                "total": total_shifts,
                "currentPage": page,
                "pageSize": limit,
                "totalPages": (total_shifts + (limit - 1)) // limit if limit else 1,
                "hasNextPage": (offset + limit) < total_shifts,
                "hasPreviousPage": page > 1,
                "register": RegisterService._serialize(RegisterService._getRegister(register_id, request)),
            },
        )

    @staticmethod
    def getShiftById(shift_id, request):
        opening = (
            commonQuery.branchScopedQueryset(RegistersHistory, {"id": shift_id}, request)
            .exclude(status=2)
            .first()
        )
        if not opening or opening.entry_type != RegistersHistory.ACTION_OPENING:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Shift not found.")

        register_id = opening.register_id

        closing = (
            commonQuery.branchScopedQueryset(
                RegistersHistory,
                {
                    "register_id": register_id,
                    "entry_type": RegistersHistory.ACTION_CLOSING,
                    "created_at__gt": opening.created_at,
                },
                request,
            )
            .exclude(status=2)
            .order_by("created_at")
            .first()
        )

        if closing:
            status = "closed"
            closed_at = closing.created_at
            declared_cash = closing.amount
            expected_cash = closing.balance_before
            difference_amount = closing.amount - closing.balance_before
            entries_qs = commonQuery.branchScopedQueryset(
                RegistersHistory,
                {
                    "register_id": register_id,
                    "created_at__gte": opening.created_at,
                    "created_at__lte": closing.created_at,
                },
                request,
            ).exclude(status=2).order_by("created_at")
        else:
            status = "active"
            closed_at = None
            declared_cash = None
            reg = commonQuery.branchScopedQueryset(Register, {"id": register_id}, request).first()
            expected_cash = reg.balance if reg else 0
            difference_amount = 0
            entries_qs = commonQuery.branchScopedQueryset(
                RegistersHistory,
                {
                    "register_id": register_id,
                    "created_at__gte": opening.created_at,
                },
                request,
            ).exclude(status=2).order_by("created_at")

        entries = []
        for entry in entries_qs:
            payment_type = "Cash"
            if entry.entry_type == RegistersHistory.ACTION_ORDER_PAYMENT and entry.payment_id:
                from apps.sales.models import OrderPayment

                pmt = commonQuery.branchScopedQueryset(OrderPayment, {"id": entry.payment_id}, request).first()
                if pmt:
                    payment_type = pmt.identifier.replace("-payment", "").title()

            entries.append(
                {
                    "id": entry.id,
                    "entry_type": entry.get_entry_type_display(),
                    "payment_type": payment_type,
                    "amount": float(entry.amount),
                    "balance_before": float(entry.balance_before),
                    "balance_after": float(entry.balance_after),
                    "reference_type": entry.entry_type,
                    "note": entry.note or "",
                    "created_at": entry.created_at,
                }
            )

        totals_by_type = []
        from django.db.models import Sum

        summed = entries_qs.values("entry_type").annotate(total=Sum("amount"))
        for item in summed:
            totals_by_type.append(
                {
                    "entry_type": item["entry_type"].replace("-", "_").replace("register_", ""),
                    "total": float(item["total"] or 0),
                }
            )

        sales_collected = entries_qs.filter(entry_type=RegistersHistory.ACTION_ORDER_PAYMENT).aggregate(total=Sum("amount"))["total"] or 0
        refund_out = entries_qs.filter(entry_type=RegistersHistory.ACTION_REFUND).aggregate(total=Sum("amount"))["total"] or 0
        cash_in = entries_qs.filter(entry_type=RegistersHistory.ACTION_CASHING).aggregate(total=Sum("amount"))["total"] or 0
        cash_out = entries_qs.filter(entry_type=RegistersHistory.ACTION_CASHOUT).aggregate(total=Sum("amount"))["total"] or 0

        return successResponse(
            "Shift details retrieved.",
            data={
                "id": opening.id,
                "register_name": opening.register.name,
                "cashier_name": opening.user.full_name or opening.user.username if opening.user else "System",
                "shift_status": status,
                "opened_at": opening.created_at,
                "closed_at": closed_at,
                "entry_count": len(entries),
                "z_report": {
                    "opening_cash": float(opening.amount),
                    "expected_cash": float(expected_cash),
                    "declared_cash": float(declared_cash) if declared_cash is not None else None,
                    "difference_amount": float(difference_amount),
                    "sales_collected": float(sales_collected),
                    "refund_out": float(refund_out),
                    "cash_in": float(cash_in),
                    "cash_out": float(cash_out),
                    "totals_by_type": totals_by_type,
                },
                "entries": entries,
            },
        )
