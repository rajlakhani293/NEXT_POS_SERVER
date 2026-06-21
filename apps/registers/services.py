# type: ignore
from types import SimpleNamespace

from django.db import transaction
from django.db.models import Sum

from apps.accounts.models import User
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import decimalValue as money
from apps.common.responses import successResponse
from apps.registers.models import Register, RegistersHistory


class RegisterService:
    @staticmethod
    def requestFromJob(job):
        user = User.objects.select_related("company", "branch").get(id=job.user_id)
        return SimpleNamespace(user=user)

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
            Register.objects.filter(id=register.id).update(register_status=Register.STATUS_CLOSED, used_by=None, balance=0)
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
            RegistersHistory.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                register_id=register.id,
                entry_type=RegistersHistory.ACTION_OPENING,
            )
            .exclude(status=2)
            .order_by("-id")
            .first()
        )
        if last_opening is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Register opening history not found.")

        base_queryset = RegistersHistory.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            register_id=register.id,
            created_at__gte=last_opening.created_at,
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
            OrderPayment.objects.select_related("sale_order")
            .filter(
                id=payment_id,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
            )
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
            payment_type_id=0,
            order_id=payment.sale_order_id,
        )
        return successResponse("Cash register payment recorded successfully.", data=history)

    @staticmethod
    def recordOrderChange(order_id, request):
        from apps.sales.models import Order

        sale_order = (
            Order.objects.filter(
                id=order_id,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
            )
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
            order_id=sale_order.id,
        )
        return successResponse("Cash register change recorded successfully.", data=history)

    @staticmethod
    def deleteRegisterHistoryUsingOrder(order_id, request):
        histories = RegistersHistory.objects.filter(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            order_id=order_id,
        ).exclude(status=2)
        register_ids = list(histories.values_list("register_id", flat=True).distinct())
        deleted_count = histories.delete()[0]
        for register_id in register_ids:
            register = Register.objects.filter(
                id=register_id,
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
            ).first()
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
