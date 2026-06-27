# type: ignore
import json
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from apps.common.commonQuery import commonQuery
from apps.common.responses import successResponse
from apps.common.exceptions import api_error
from apps.common.error_codes import ErrorCodes
from apps.accounting.models import TransactionAccount, Transaction
from apps.registers.models import Register, RegistersHistory
from apps.registers.services import RegisterService
from apps.sales.services import getCurrentRegisterContext


def serialize_description(payment_type, shift_id, reference_number, note):
    payload = {
        "payment_type": payment_type,
        "shift_id": shift_id,
        "reference_number": reference_number,
        "note": note,
    }
    return json.dumps(payload)


def deserialize_description(description_str):
    try:
        data = json.loads(description_str)
        if isinstance(data, dict):
            return {
                "payment_type": data.get("payment_type", "cash-payment"),
                "shift_id": data.get("shift_id"),
                "reference_number": data.get("reference_number", ""),
                "note": data.get("note", ""),
            }
    except Exception:
        pass
    return {
        "payment_type": "cash-payment",
        "shift_id": None,
        "reference_number": "",
        "note": description_str or "",
    }


class ExpenseCategoryService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            name = data["name"]
            category_identifier = "expenses"
            
            siblings = commonQuery.countRecords(
                TransactionAccount,
                {"category_identifier": category_identifier},
                request=request,
                tenant_config=True,
            )
            account_code = f"{str(siblings + 1).zfill(4)}-{category_identifier}-{name.lower().replace(' ', '-')}"

            category = commonQuery.createRecord(
                TransactionAccount,
                {
                    "name": name,
                    "description": data.get("description") or "",
                    "category_identifier": category_identifier,
                    "account": account_code,
                },
                request=request,
                tenant_config=True,
            )
            return successResponse("Expense category created successfully.", data={
                "id": category["id"],
                "name": category["name"],
                "description": category["description"],
                "status": category["status"],
            })

    @staticmethod
    def edit(category_id, data, request):
        with transaction.atomic():
            category = commonQuery.updateRecordById(
                TransactionAccount,
                category_id,
                {
                    "name": data["name"],
                    "description": data.get("description") or "",
                },
                request=request,
                tenant_config=True,
            )
            if category is None or category.get("category_identifier") != "expenses":
                raise api_error(404, ErrorCodes.NOT_FOUND, "Expense category not found.")
            return successResponse("Expense category updated successfully.", data={
                "id": category["id"],
                "name": category["name"],
                "description": category["description"],
                "status": category["status"],
            })

    @staticmethod
    def delete(data, request):
        ids = data.get("ids", [])
        if not ids:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "No IDs provided.")
        with transaction.atomic():
            for cat_id in ids:
                cat = commonQuery.findOneRecord(TransactionAccount, cat_id, request=request, tenant_config=True)
                if not cat or cat.get("category_identifier") != "expenses":
                    raise api_error(404, ErrorCodes.NOT_FOUND, f"Expense category {cat_id} not found.")

            deleted_count = commonQuery.softDeleteById(
                TransactionAccount,
                ids,
                request=request,
                tenant_config=True,
            )
            if deleted_count == 0:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Expense categories not found.")
            return successResponse("Expense categories deleted successfully.", data={"deleted_count": deleted_count})

    @staticmethod
    def updateStatus(data, request):
        ids = data.get("ids", [])
        status = data.get("status")
        if status is None:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status is required.")
        with transaction.atomic():
            for cat_id in ids:
                cat = commonQuery.findOneRecord(TransactionAccount, cat_id, request=request, tenant_config=True)
                if not cat or cat.get("category_identifier") != "expenses":
                    raise api_error(404, ErrorCodes.NOT_FOUND, f"Expense category {cat_id} not found.")

            updated_count = commonQuery.updateStatusById(
                TransactionAccount,
                ids,
                status,
                request=request,
                tenant_config=True,
            )
            if updated_count == 0:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Expense categories not found.")
            return successResponse("Expense category status updated successfully.", data={"updated_count": updated_count, "status": status})

    @staticmethod
    def getById(category_id, request):
        category = commonQuery.findOneRecord(
            TransactionAccount,
            category_id,
            request=request,
            tenant_config=True,
        )
        if category is None or category.get("category_identifier") != "expenses" or category.get("status") == 2:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense category not found.")
        return successResponse("Expense category retrieved successfully.", data={
            "id": category["id"],
            "name": category["name"],
            "description": category["description"],
            "status": category["status"],
        })

    @staticmethod
    def getAll(data, request):
        page = max(int((data or {}).get("page", 1)), 1)
        limit = int((data or {}).get("limit", 10))
        offset = (page - 1) * limit
        search = (data or {}).get("search", "")

        qs = commonQuery.branchScopedQueryset(TransactionAccount, {"category_identifier": "expenses"}, request).exclude(status=2)
        if search:
            qs = qs.filter(name__icontains=search)

        total = qs.count()
        items = list(
            qs.order_by("name")[offset : offset + limit].values(
                "id", "name", "description", "status", "created_at", "account", "user__username"
            )
        )
        for item in items:
            item["user_username"] = item.pop("user__username", None)

        return successResponse(
            "Expense categories retrieved successfully.",
            data={
                "items": items,
                "total": total,
                "currentPage": page,
                "pageSize": limit,
                "totalPages": (total + (limit - 1)) // limit if limit else 1,
                "hasNextPage": (offset + limit) < total,
                "hasPreviousPage": page > 1,
            },
        )

    @staticmethod
    def dropdownList(request):
        qs = commonQuery.branchScopedQueryset(TransactionAccount, {"category_identifier": "expenses", "status": 0}, request)
        items = list(qs.order_by("name").values("id", "name"))
        return successResponse("Expense categories dropdown list retrieved.", data=items)


class ExpenseService:
    @staticmethod
    def create(data, request):
        amount = Decimal(str(data["amount"]))
        category_id = data["category_id"]
        payment_type = data.get("payment_type", "cash-payment")
        shift_id = data.get("shift_id")
        expense_date = data["expense_date"]
        reference_number = data.get("reference_number", "")
        note = data.get("note", "")

        with transaction.atomic():
            category = commonQuery.findOneRecord(
                TransactionAccount,
                category_id,
                request=request,
                tenant_config=True,
            )
            if not category or category.get("category_identifier") != "expenses" or category.get("status") == 2:
                raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid expense category.")

            shift = None
            register_id = None
            if shift_id:
                opening = commonQuery.branchScopedQueryset(
                    RegistersHistory,
                    {"id": shift_id, "entry_type": RegistersHistory.ACTION_OPENING},
                    request,
                ).first()
                if opening:
                    shift = opening
                    register_id = opening.register_id
                else:
                    opening = commonQuery.branchScopedQueryset(
                        RegistersHistory,
                        {"register_id": shift_id, "entry_type": RegistersHistory.ACTION_OPENING},
                        request,
                    ).exclude(status=2).order_by("-id").first()
                    if opening:
                        shift = opening
                        register_id = opening.register_id

            if not shift and payment_type == "cash-payment":
                reg_context = getCurrentRegisterContext(request, required=True)
                register_id = reg_context["register_id"]
                opening = commonQuery.branchScopedQueryset(
                    RegistersHistory,
                    {"register_id": register_id, "entry_type": RegistersHistory.ACTION_OPENING},
                    request,
                ).exclude(status=2).order_by("-id").first()
                if not opening:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Open cash register is required.")
                shift = opening

            desc_str = serialize_description(payment_type, shift.id if shift else None, reference_number, note)
            expense_name = data.get("name") or f"Expense: {category.get('name')}"

            expense = commonQuery.createRecord(
                Transaction,
                {
                    "name": expense_name,
                    "account_id": category_id,
                    "value": amount,
                    "description": desc_str,
                    "type": Transaction.TYPE_DIRECT,
                    "active": True,
                    "scheduled_date": expense_date + " 00:00:00" if isinstance(expense_date, str) else expense_date,
                },
                request=request,
                tenant_config=True,
            )

            if payment_type == "cash-payment" and register_id:
                RegisterService.recordHistory(
                    register_id=register_id,
                    action=RegistersHistory.ACTION_CASHOUT,
                    amount=amount,
                    request=request,
                    note=f"Expense: {category.get('name')}. {note}",
                    payment_id=expense["id"],
                )

            return successResponse("Expense recorded successfully.", data={
                "id": expense["id"],
                "category_id": category_id,
                "amount": float(amount),
                "expense_date": expense_date,
                "payment_type": payment_type,
                "shift_id": shift.id if shift else None,
                "reference_number": reference_number,
                "note": note,
            })

    @staticmethod
    def edit(expense_id, data, request):
        amount = Decimal(str(data["amount"])) if "amount" in data and data["amount"] is not None else None
        category_id = data.get("category_id")
        payment_type = data.get("payment_type")
        shift_id = data.get("shift_id")
        expense_date = data.get("expense_date")
        reference_number = data.get("reference_number")
        note = data.get("note")

        with transaction.atomic():
            expense_record = commonQuery.findOneRecord(
                Transaction,
                expense_id,
                request=request,
                tenant_config=True,
            )
            if expense_record is None or expense_record.get("status") == 2:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Expense not found.")
            
            cat_id = category_id if category_id is not None else expense_record.get("account_id")
            category = commonQuery.findOneRecord(TransactionAccount, cat_id, request=request, tenant_config=True)
            if not category or category.get("category_identifier") != "expenses":
                raise api_error(404, ErrorCodes.NOT_FOUND, "Invalid expense category.")

            pos_fields = deserialize_description(expense_record.get("description"))
            old_amount = Decimal(str(expense_record.get("value")))
            old_payment_type = pos_fields["payment_type"]
            old_shift_id = pos_fields["shift_id"]

            old_history = None
            if old_payment_type == "cash-payment" and old_shift_id:
                old_opening = RegistersHistory.objects.filter(id=old_shift_id).first()
                if old_opening:
                    old_history = RegistersHistory.objects.filter(
                        register_id=old_opening.register_id,
                        payment_id=expense_record["id"],
                        entry_type=RegistersHistory.ACTION_CASHOUT
                    ).first()

            if old_history:
                reg = Register.objects.select_for_update().get(id=old_history.register_id)
                reg.balance += old_history.amount
                reg.save(update_fields=["balance"])
                old_history.delete()

            shift = None
            register_id = None
            new_payment_type = payment_type if payment_type is not None else old_payment_type
            new_shift_id = shift_id if shift_id is not None else old_shift_id

            if new_shift_id:
                opening = commonQuery.branchScopedQueryset(
                    RegistersHistory,
                    {"id": new_shift_id, "entry_type": RegistersHistory.ACTION_OPENING},
                    request,
                ).first()
                if opening:
                    shift = opening
                    register_id = opening.register_id
                else:
                    opening = commonQuery.branchScopedQueryset(
                        RegistersHistory,
                        {"register_id": new_shift_id, "entry_type": RegistersHistory.ACTION_OPENING},
                        request,
                    ).exclude(status=2).order_by("-id").first()
                    if opening:
                        shift = opening
                        register_id = opening.register_id

            if not shift and new_payment_type == "cash-payment":
                reg_context = getCurrentRegisterContext(request, required=True)
                register_id = reg_context["register_id"]
                opening = commonQuery.branchScopedQueryset(
                    RegistersHistory,
                    {"register_id": register_id, "entry_type": RegistersHistory.ACTION_OPENING},
                    request,
                ).exclude(status=2).order_by("-id").first()
                if not opening:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Open cash register is required.")
                shift = opening

            final_payment_type = payment_type if payment_type is not None else old_payment_type
            final_shift_id = shift.id if shift else (new_shift_id if new_shift_id is not None else old_shift_id)
            final_reference_number = reference_number if reference_number is not None else pos_fields["reference_number"]
            final_note = note if note is not None else pos_fields["note"]

            new_desc = serialize_description(final_payment_type, final_shift_id, final_reference_number, final_note)

            updates = {}
            if category_id is not None:
                updates["account_id"] = category_id
            if data.get("name"):
                updates["name"] = data["name"]
            elif category_id is not None:
                updates["name"] = f"Expense: {category.get('name')}"
            if amount is not None:
                updates["value"] = amount
            if expense_date is not None:
                updates["scheduled_date"] = expense_date + " 00:00:00" if isinstance(expense_date, str) else expense_date
            
            updates["description"] = new_desc

            updated_expense = commonQuery.updateRecordById(
                Transaction,
                expense_id,
                updates,
                request=request,
                tenant_config=True,
            )

            if final_payment_type == "cash-payment" and register_id:
                final_amount = amount if amount is not None else old_amount
                RegisterService.recordHistory(
                    register_id=register_id,
                    action=RegistersHistory.ACTION_CASHOUT,
                    amount=final_amount,
                    request=request,
                    note=f"Expense: {category.get('name')}. {final_note}",
                    payment_id=updated_expense["id"],
                )

            return successResponse("Expense updated successfully.", data={
                "id": updated_expense["id"],
                "category_id": cat_id,
                "amount": float(amount if amount is not None else old_amount),
                "expense_date": str(expense_date if expense_date is not None else (expense_record.get("scheduled_date") or "")).split(" ")[0],
                "payment_type": final_payment_type,
                "shift_id": final_shift_id,
                "reference_number": final_reference_number,
                "note": final_note,
            })

    @staticmethod
    def delete(data, request):
        ids = data.get("ids", [])
        if not ids:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "No IDs provided.")
        with transaction.atomic():
            expenses_to_delete = Transaction.objects.filter(id__in=ids)
            for exp in expenses_to_delete:
                pos_fields = deserialize_description(exp.description)
                if pos_fields["payment_type"] == "cash-payment" and pos_fields["shift_id"]:
                    hist = RegistersHistory.objects.filter(
                        payment_id=exp.id,
                        entry_type=RegistersHistory.ACTION_CASHOUT
                    ).first()
                    if hist:
                        reg = Register.objects.select_for_update().get(id=hist.register_id)
                        reg.balance += hist.amount
                        reg.save(update_fields=["balance"])
                        hist.delete()

            deleted_count = commonQuery.softDeleteById(
                Transaction,
                ids,
                request=request,
                tenant_config=True,
            )
            if deleted_count == 0:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Expenses not found.")
            return successResponse("Expenses deleted successfully.", data={"deleted_count": deleted_count})

    @staticmethod
    def updateStatus(data, request):
        ids = data.get("ids", [])
        status = data.get("status")
        if status is None:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Status is required.")
        with transaction.atomic():
            updated_count = commonQuery.updateStatusById(
                Transaction,
                ids,
                status,
                request=request,
                tenant_config=True,
            )
            if updated_count == 0:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Expenses not found.")
            return successResponse("Expense status updated successfully.", data={"updated_count": updated_count, "status": status})

    @staticmethod
    def getById(expense_id, request):
        exp = commonQuery.findOneRecord(
            Transaction,
            expense_id,
            request=request,
            tenant_config=True,
        )
        if exp is None or exp.get("status") == 2:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Expense not found.")
        
        pos_fields = deserialize_description(exp.get("description"))
        exp_date_str = str(exp.get("scheduled_date") or "").split(" ")[0]
        
        data = {
            "id": exp.get("id"),
            "name": exp.get("name"),
            "category_id": exp.get("account_id"),
            "amount": float(exp.get("value")),
            "expense_date": exp_date_str,
            "payment_type": pos_fields["payment_type"],
            "shift_id": pos_fields["shift_id"],
            "reference_number": pos_fields["reference_number"],
            "note": pos_fields["note"],
            "status": exp.get("status"),
        }
        return successResponse("Expense retrieved successfully.", data=data)

    @staticmethod
    def getAll(data, request):
        page = max(int((data or {}).get("page", 1)), 1)
        limit = int((data or {}).get("limit", 10))
        offset = (page - 1) * limit
        search = (data or {}).get("search", "")

        expense_accounts = TransactionAccount.objects.filter(category_identifier="expenses").values_list("id", flat=True)
        qs = (
            commonQuery.branchScopedQueryset(Transaction, {"account_id__in": list(expense_accounts)}, request)
            .exclude(status=2)
            .select_related("user", "account")
        )

        if search:
            qs = qs.filter(
                Q(description__icontains=search) |
                Q(account__name__icontains=search)
            )

        total = qs.count()
        paginated_qs = qs.order_by("-scheduled_date", "-id")[offset : offset + limit]

        shift_ids = []
        deserialized_list = []
        for exp in paginated_qs:
            pos = deserialize_description(exp.description)
            deserialized_list.append((exp, pos))
            if pos["shift_id"]:
                shift_ids.append(pos["shift_id"])

        shifts_map = {}
        if shift_ids:
            openings = RegistersHistory.objects.filter(id__in=shift_ids).select_related("register")
            for op in openings:
                closing_exists = RegistersHistory.objects.filter(
                    register_id=op.register_id,
                    entry_type=RegistersHistory.ACTION_CLOSING,
                    created_at__gt=op.created_at
                ).exclude(status=2).exists()
                shifts_map[op.id] = {
                    "register_name": op.register.name if op.register else "-",
                    "status": "closed" if closing_exists else "active"
                }

        items = []
        for exp, pos in deserialized_list:
            shift_id = pos["shift_id"]
            register_name = "-"
            shift_status = "-"
            if shift_id in shifts_map:
                register_name = shifts_map[shift_id]["register_name"]
                shift_status = shifts_map[shift_id]["status"]

            exp_date_str = str(exp.scheduled_date or "").split(" ")[0]

            items.append({
                "id": exp.id,
                "name": exp.name,
                "category_id": exp.account_id,
                "category__name": exp.account.name if exp.account else "-",
                "amount": float(exp.value),
                "expense_date": exp_date_str,
                "payment_type": pos["payment_type"],
                "shift_id": shift_id,
                "shift__register__name": register_name,
                "shift__shift_status": shift_status,
                "reference_number": pos["reference_number"],
                "note": pos["note"],
                "status": exp.status,
                "user_username": exp.user.username if exp.user else "-",
                "created_at": exp.created_at.isoformat() if exp.created_at else None,
            })

        return successResponse(
            "Expenses retrieved successfully.",
            data={
                "items": items,
                "total": total,
                "currentPage": page,
                "pageSize": limit,
                "totalPages": (total + (limit - 1)) // limit if limit else 1,
                "hasNextPage": (offset + limit) < total,
                "hasPreviousPage": page > 1,
            },
        )
