# type: ignore
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

from apps.accounts.models import Role, User, UserRoleRelation
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import validateTenantRelationId
from apps.common.responses import successResponse
from apps.customers.models import (
    CUSTOMER_ROLE_CODE,
    Customer,
    CustomerAccountHistory,
    CustomerAddress,
    CustomerCoupon,
    CustomerGroup,
    CustomerReward,
)
from apps.rewards.models import RewardSystem


ADDRESS_FIELDS = [
    "email",
    "first_name",
    "last_name",
    "phone",
    "address_1",
    "address_2",
    "country",
    "pobox",
    "city",
    "company_name",
    "company",
]
ADDRESS_TYPES = ["billing", "shipping"]


def buildCustomerDisplayName(data):
    return f"{data.get('first_name') or ''} {data.get('last_name') or ''}".strip()


def buildUniqueCustomerUsername(data):
    base = slugify(
        data.get("email")
        or data.get("phone")
        or buildCustomerDisplayName(data)
        or "customer"
    ) or "customer"
    username = base
    counter = 1
    while commonQuery.existsRecord(User, {"username": username}, tenant_config={}):
        counter += 1
        username = f"{base}-{counter}"
    return username


def getOrCreateCustomerRole(request):
    role = Role.findByNamespace(
        CUSTOMER_ROLE_CODE,
        getattr(request.user, "company_id", None),
        getattr(request.user, "branch_id", None),
    )
    if role is not None:
        return role

    role = commonQuery.branchScopedQueryset(
        Role,
        {"name": "Store Customer", "status__in": [0, 1]},
        request,
    ).first()
    if role is not None:
        updates = []
        if role.namespace != CUSTOMER_ROLE_CODE:
            role.namespace = CUSTOMER_ROLE_CODE
            updates.append("namespace")
        if not role.locked:
            role.locked = True
            updates.append("locked")
        if updates:
            role.save(update_fields=updates)
        return role

    role, _created = commonQuery.getOrCreateRecord(
        Role,
        {"namespace": CUSTOMER_ROLE_CODE},
        defaults={
            "name": "Store Customer",
            "locked": True,
            "description": "Customer account used for POS orders, rewards, coupons, and account history.",
        },
        request=request,
        tenant_config=True,
        return_plain=False,
    )
    return role


def assignCustomerRole(user, role):
    relation, _created = commonQuery.getOrCreateRecord(
        UserRoleRelation,
        {
            "user_id": user.id,
            "role_id": role.id,
        },
        defaults={
            "company_id": user.company_id,
            "branch_id": user.branch_id,
            "status": 0,
        },
        tenant_config={},
        return_plain=False,
    )
    if relation.status != 0:
        relation.status = 0
        relation.deleted_at = None
        relation.save(update_fields=["status", "deleted_at"])


def splitCustomerData(data):
    customer_data = dict(data or {})
    address_data = {}
    for address_type in ADDRESS_TYPES:
        address_data[address_type] = {}
        for field in ADDRESS_FIELDS:
            source_key = f"{address_type}_{field}"
            if source_key in customer_data:
                target_field = "company_name" if field == "company" else field
                value = customer_data.pop(source_key)
                value = "" if value is None else value
                if value != "" or target_field not in address_data[address_type]:
                    address_data[address_type][target_field] = value
    birth_date = customer_data.get("birth_date")
    if birth_date == "":
        customer_data["birth_date"] = None
    return customer_data, address_data


def hydrateCustomer(customer, request):
    customer_data = dict(customer)
    customer_data["group_name"] = None
    if customer_data.get("group_id"):
        group = commonQuery.findOneRecord(
            CustomerGroup,
            customer_data["group_id"],
            options={"attributes": ["name"]},
            request=request,
            tenant_config=True,
        )
        customer_data["group_name"] = group["name"] if group else None

    address_records = commonQuery.findAllRecords(
        CustomerAddress,
        {"customer_id": customer_data["id"]},
        {"order": ["type"]},
        request=request,
        tenant_config=True,
    )
    addresses = {address_type: None for address_type in ADDRESS_TYPES}
    for address in address_records:
        addresses[address["type"]] = address
    customer_data["addresses"] = addresses
    customer_data["address"] = addresses.get("billing")
    for address in addresses.values():
        if address and "company" not in address:
            address["company"] = address.get("company_name") or ""
    return customer_data


def upsertCustomerAddress(customer_id, address_type, address_data, request):
    if not any(value for value in address_data.values()):
        return None

    existing = commonQuery.findOneRecord(
        CustomerAddress,
        {"customer_id": customer_id, "type": address_type},
        request=request,
        tenant_config=True,
    )
    payload = {
        **address_data,
        "customer_id": customer_id,
        "type": address_type,
    }
    if existing:
        return commonQuery.updateRecordById(
            CustomerAddress,
            existing["id"],
            payload,
            request=request,
            tenant_config=True,
        )
    return commonQuery.createRecord(
        CustomerAddress,
        payload,
        request=request,
        tenant_config=True,
    )


class CustomerService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            customer_data, address_data = splitCustomerData(data)
            if customer_data.get("group_id"):
                validateTenantRelationId(
                    CustomerGroup,
                    customer_data["group_id"],
                    request=request,
                    label="Customer group",
                    tenant_config=True,
                )

            customer_data["username"] = customer_data.get("username") or buildUniqueCustomerUsername(customer_data)
            customer_data["full_name"] = customer_data.get("full_name") or buildCustomerDisplayName(customer_data)
            customer_role = getOrCreateCustomerRole(request)
            customer_data["role_id"] = customer_role.id
            customer_data["company_id"] = getattr(request.user, "company_id", None)
            customer_data["branch_id"] = getattr(request.user, "branch_id", None)

            customer_instance = Customer.objects.create_user(
                password=None,
                **customer_data,
            )
            assignCustomerRole(customer_instance, customer_role)
            customer = commonQuery.findOneRecord(
                Customer,
                customer_instance.id,
                request=request,
                tenant_config=True,
            )
            for address_type, payload in address_data.items():
                upsertCustomerAddress(customer["id"], address_type, payload, request)
            return successResponse(
                "Customer created successfully.",
                data=hydrateCustomer(customer, request),
            )

    @staticmethod
    def getAll(data, request):
        fieldConfig = [
            ["first_name", True, True],
            ["last_name", True, True],
            ["phone", True, True],
            ["email", True, True],
        ]
        options = {
            "attributes": [
                "id",
                "first_name",
                "last_name",
                "phone",
                "email",
                "pobox",
                "purchases_amount",
                "credit_limit_amount",
                "owed_amount",
                "account_amount",
                "status",
                "group_id",
                "username",
                "date_joined",
            ],
        }
        result = commonQuery.fetchPaginatedData(
            Customer,
            data,
            fieldConfig,
            options,
            request=request,
            tenant_config=True,
        )
        group_ids = {item.get("group_id") for item in result.get("items", []) if item.get("group_id")}
        group_map = {}
        if group_ids:
            groups = CustomerGroup.objects.filter(id__in=group_ids).values("id", "name")
            group_map = {g["id"]: g["name"] for g in groups}

        for item in result.get("items", []):
            item["name"] = f"{item.get('first_name') or ''} {item.get('last_name') or ''}".strip()
            item["group_name"] = group_map.get(item.get("group_id"))
            item["user_username"] = item.get("username")
            item["created_at"] = item.pop("date_joined", None)
        return successResponse("Customers retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        customers = commonQuery.findAllRecords(
            Customer,
            {},
            {
                "attributes": ["id", "first_name", "last_name", "phone"],
                "order": ["first_name", "last_name"],
            },
            request=request,
            tenant_config=True,
        )
        data = [
            {
                "id": customer["id"],
                "name": f"{customer.get('first_name') or ''} {customer.get('last_name') or ''}".strip()
                or customer.get("phone")
                or f"Customer #{customer['id']}",
                "phone": customer.get("phone"),
            }
            for customer in customers
        ]
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def groupDropdownList(request):
        data = commonQuery.findAllRecords(
            CustomerGroup,
            {},
            {"attributes": ["id", "name"], "order": ["name"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Dropdown list retrieved successfully.", data=data)

    @staticmethod
    def getById(customer_id, request):
        customer = commonQuery.findOneRecord(
            Customer,
            customer_id,
            request=request,
            tenant_config=True,
        )
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        return successResponse("Customer retrieved successfully.", data=hydrateCustomer(customer, request))

    @staticmethod
    def recentlyActive(limit, request):
        limit = int(limit or 10)
        customers = (
            commonQuery.branchScopedQueryset(Customer, {"group_id__isnull": False, "status": 0}, request)
            .order_by("-updated_at")[:limit]
        )
        data = [
            hydrateCustomer(
                commonQuery.findOneRecord(Customer, customer.id, request=request, tenant_config=True),
                request,
            )
            for customer in customers
        ]
        return successResponse("Recently active customers retrieved successfully.", data=data)

    @staticmethod
    def search(data, request):
        argument = str((data or {}).get("search") or "")
        queryset = commonQuery.branchScopedQueryset(Customer, {"status": 0}, request)
        if argument:
            queryset = queryset.filter(
                Q(first_name__icontains=argument)
                | Q(last_name__icontains=argument)
                | Q(email__icontains=argument)
                | Q(phone__icontains=argument)
            )
        customers = queryset.order_by("first_name", "last_name")[:10]
        data = [
            hydrateCustomer(
                commonQuery.findOneRecord(Customer, customer.id, request=request, tenant_config=True),
                request,
            )
            for customer in customers
        ]
        return successResponse("Customers retrieved successfully.", data=data)

    @staticmethod
    def deleteUsingEmail(email, request):
        customer = commonQuery.branchScopedQueryset(Customer, {"email": email, "status": 0}, request).first()
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        return CustomerService.delete({"ids": [customer.id]}, request)

    @staticmethod
    def addresses(customer_id, request):
        customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        data = commonQuery.findAllRecords(
            CustomerAddress,
            {"customer_id": customer_id},
            {"order": ["type"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Customer addresses retrieved successfully.", data=data)

    @staticmethod
    def group(customer_id, request):
        customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        group_id = customer.get("group_id")
        if not group_id:
            return successResponse("Customer group retrieved successfully.", data=None)
        group = commonQuery.findOneRecord(CustomerGroup, group_id, request=request, tenant_config=True)
        return successResponse("Customer group retrieved successfully.", data=group)

    @staticmethod
    def coupons(customer_id, request):
        customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        data = commonQuery.findAllRecords(
            CustomerCoupon,
            {"customer_id": customer_id},
            {"order": ["-created_at"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Customer coupons retrieved successfully.", data=data)

    @staticmethod
    def rewards(customer_id, request):
        customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        data = commonQuery.findAllRecords(
            CustomerReward,
            {"customer_id": customer_id},
            {"order": ["-created_at"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Customer rewards retrieved successfully.", data=data)

    @staticmethod
    def update(data, request, customer_id):
        with transaction.atomic():
            customer = commonQuery.findOneRecord(
                Customer,
                customer_id,
                request=request,
                tenant_config=True,
            )
            if customer is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")

            customer_data, address_data = splitCustomerData(data)
            if customer_data.get("group_id"):
                validateTenantRelationId(
                    CustomerGroup,
                    customer_data["group_id"],
                    request=request,
                    label="Customer group",
                    tenant_config=True,
                )

            customer_data = commonQuery.updateRecordById(
                Customer,
                customer_id,
                customer_data,
                request=request,
                tenant_config=True,
            )
            if customer_data is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
            for address_type, payload in address_data.items():
                upsertCustomerAddress(customer_id, address_type, payload, request)
            return successResponse(
                "Customer updated successfully.",
                data=hydrateCustomer(customer_data, request),
            )

    @staticmethod
    def delete(data, request):
        ids = data.get("ids")
        if not isinstance(ids, list):
            ids = [ids]
        commonQuery.softDeleteById(
            CustomerAddress,
            {"customer_id__in": ids},
            request=request,
            tenant_config=True,
        )
        count = commonQuery.softDeleteById(
            Customer,
            ids,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        return successResponse("Customers deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(
            Customer,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        return successResponse(
            "Customer status updated successfully.",
            data={"updated_count": count, "status": status},
        )

    @staticmethod
    def adjustCredit(customer_id, data, request):
        from decimal import Decimal

        amount = Decimal(str(data.get("amount") or 0))
        direction = data.get("direction")
        if direction not in ["increase", "decrease"]:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Direction must be increase or decrease.")
        if amount <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Amount must be greater than 0.")

        with transaction.atomic():
            customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
            if customer is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
            current_balance = Decimal(str(customer.get("owed_amount") or 0))
            balance_after = current_balance + amount if direction == "increase" else current_balance - amount
            updated = commonQuery.updateRecordById(
                Customer,
                customer_id,
                {"owed_amount": balance_after},
                request=request,
                tenant_config=True,
            )
            ledger = commonQuery.createRecord(
                CustomerAccountHistory,
                {
                    "customer_id": customer_id,
                    "amount": amount,
                    "previous_amount": current_balance,
                    "next_amount": balance_after,
                    "operation": "add" if direction == "increase" else "deduct",
                    "description": data.get("note") or data.get("reason") or "Manual adjustment",
                },
                request=request,
                tenant_config=True,
            )
            updated["credit_ledger"] = ledger
            return successResponse("Customer credit updated successfully.", data=updated)

    @staticmethod
    def accountTransaction(customer_id, data, request):
        general = data.get("general") or {}
        return CustomerAccountService.saveTransaction(
            customer_id,
            data.get("operation") or general.get("operation"),
            data.get("amount") or general.get("amount"),
            request,
            data.get("description") or general.get("description") or "",
        )

    @staticmethod
    def creditLedger(customer_id, data, request):
        customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        result = commonQuery.fetchPaginatedData(
            CustomerAccountHistory,
            data,
            [["operation", True, True], ["description", True, True]],
            {
                "attributes": [
                    "id",
                    "customer_id",
                    "amount",
                    "operation",
                    "previous_amount",
                    "next_amount",
                    "description",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
            custom_where={"customer_id": customer_id},
        )
        return successResponse("Customer credit ledger retrieved successfully.", data=result)

    @staticmethod
    def orderHistory(customer_id, data, request):
        customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        from apps.sales.models import Order
        result = commonQuery.fetchPaginatedData(
            Order,
            data,
            [["code", True, True], ["payment_status", True, True], ["order_type", True, True]],
            {
                "attributes": [
                    "id",
                    "code",
                    "order_type",
                    "payment_status",
                    "process_status",
                    "delivery_status",
                    "subtotal",
                    "tax_amount",
                    "shipping",
                    "total",
                    "created_at",
                ]
            },
            request=request,
            tenant_config=True,
            custom_where={"customer_id": customer_id},
        )
        return successResponse("Customer order history retrieved successfully.", data=result)



class CustomerAccountService:
    DEDUCT_OPERATIONS = ["deduct", "payment"]
    ADD_OPERATIONS = ["add", "refund"]
    OPERATIONS = DEDUCT_OPERATIONS + ADD_OPERATIONS

    @staticmethod
    def requestFromJob(job):
        from apps.common.helpers import requestFromJobUser

        return requestFromJobUser(job)

    @staticmethod
    def decimalAmount(value):
        return Decimal(str(value or 0))

    @staticmethod
    def canReduceCustomerAccount(customer_id, amount, request):
        amount = CustomerAccountService.decimalAmount(amount)
        customer = commonQuery.findOneRecord(
            Customer,
            customer_id,
            request=request,
            tenant_config=True,
        )
        if customer is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")
        if CustomerAccountService.decimalAmount(customer.get("account_amount")) - amount < 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer account balance is not enough for this payment.")
        return successResponse("Customer account can be used for this payment.", data={"allowed": True})

    @staticmethod
    def saveTransaction(customer_id, operation, amount, request, description="", order_id=None):
        amount = CustomerAccountService.decimalAmount(amount)
        if operation not in CustomerAccountService.OPERATIONS:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Invalid customer account operation.")
        if amount <= 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Amount must be greater than 0.")

        with transaction.atomic():
            customer = (
                commonQuery.branchScopedQueryset(Customer, {"id": customer_id}, request)
                .select_for_update()
                .first()
            )
            if customer is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")

            latest_history = (
                commonQuery.branchScopedQueryset(
                    CustomerAccountHistory,
                    {"customer_id": customer_id, "status": 0},
                    request,
                )
                .select_for_update()
                .order_by("-id")
                .first()
            )
            previous_amount = (
                CustomerAccountService.decimalAmount(latest_history.next_amount)
                if latest_history
                else CustomerAccountService.decimalAmount(customer.account_amount)
            )
            if operation in CustomerAccountService.DEDUCT_OPERATIONS:
                next_amount = previous_amount - amount
                if next_amount < 0:
                    raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer account balance is not enough for this payment.")
            else:
                next_amount = previous_amount + amount

            history = commonQuery.createRecord(
                CustomerAccountHistory,
                {
                    "customer_id": customer_id,
                    "amount": amount,
                    "previous_amount": previous_amount,
                    "next_amount": next_amount,
                    "operation": operation,
                    "order_id": order_id,
                    "description": description or "",
                },
                request=request,
                tenant_config=True,
            )
            customer.account_amount = next_amount
            customer.save(update_fields=["account_amount"])
        return successResponse("Customer account history stored successfully.", data=history)

    @staticmethod
    def storePaymentHistory(payment_id, request):
        from apps.sales.models import OrderPayment

        if not payment_id:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Payment ID is required.")
        payment = (
            commonQuery.branchScopedQueryset(OrderPayment, {"id": payment_id, "status": 0}, request)
            .select_related("sale_order")
            .first()
        )
        if payment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Order payment not found.")
        if payment.identifier != "account-payment":
            return successResponse("Payment does not use customer account.", data={"skipped": True})
        sale_order = payment.sale_order
        if not sale_order.customer_id:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer is required for account payment.")

        existing = commonQuery.branchScopedQueryset(
            CustomerAccountHistory,
            {
                "customer_id": sale_order.customer_id,
                "order_id": sale_order.id,
                "operation": "payment",
                "amount": payment.value,
                "status": 0,
            },
            request,
        ).first()
        if existing:
            return successResponse("Customer account payment history already exists.", data={"id": existing.id})
        return CustomerAccountService.saveTransaction(
            sale_order.customer_id,
            "payment",
            payment.value,
            request,
            f"Order payment for {sale_order.code}",
            order_id=sale_order.id,
        )

    @staticmethod
    def jobHandlers():
        return {
            "check_customer_account": lambda data, job: CustomerAccountService.canReduceCustomerAccount(
                data.get("customer_id"),
                data.get("amount") or data.get("value"),
                CustomerAccountService.requestFromJob(job),
            ),
            "store_customer_payment_history": lambda data, job: CustomerAccountService.storePaymentHistory(
                data.get("payment_id") or data.get("order_payment_id"),
                CustomerAccountService.requestFromJob(job),
            ),
        }


class CustomerGroupService:
    @staticmethod
    def create(data, request):
        with transaction.atomic():
            if data.get("reward_system_id"):
                validateTenantRelationId(
                    RewardSystem,
                    data["reward_system_id"],
                    request=request,
                    label="Reward system",
                    tenant_config=True,
                )

            group = commonQuery.createRecord(
                CustomerGroup,
                data,
                request=request,
                tenant_config=True,
            )
            return successResponse("Customer group created successfully.", data=group)

    @staticmethod
    def getAll(data, request):
        fieldConfig = [["name", True, True]]
        options = {
            "attributes": [
                "id",
                "name",
                "description",
                "minimal_credit_payment",
                "reward_system_id",
                "status",
                "created_at",
                "user__username",
            ],
        }
        result = commonQuery.fetchPaginatedData(
            CustomerGroup,
            data,
            fieldConfig,
            options,
            request=request,
            tenant_config=True,
        )
        reward_ids = {item.get("reward_system_id") for item in result.get("items", []) if item.get("reward_system_id")}
        reward_map = {}
        if reward_ids:
            rewards = RewardSystem.objects.filter(id__in=reward_ids).values("id", "name")
            reward_map = {r["id"]: r["name"] for r in rewards}

        for item in result.get("items", []):
            item["reward_name"] = reward_map.get(item.get("reward_system_id")) or "N/A"
            item["user_username"] = item.pop("user__username", None)
        return successResponse("Customer groups retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        return CustomerService.groupDropdownList(request)

    @staticmethod
    def getById(group_id, request):
        group = commonQuery.findOneRecord(
            CustomerGroup,
            group_id,
            request=request,
            tenant_config=True,
        )
        if group is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer group not found.")
        return successResponse("Customer group retrieved successfully.", data=group)

    @staticmethod
    def update(data, request, group_id):
        with transaction.atomic():
            group = commonQuery.findOneRecord(
                CustomerGroup,
                group_id,
                request=request,
                tenant_config=True,
            )
            if group is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Customer group not found.")

            if data.get("reward_system_id"):
                validateTenantRelationId(
                    RewardSystem,
                    data["reward_system_id"],
                    request=request,
                    label="Reward system",
                    tenant_config=True,
                )

            updated = commonQuery.updateRecordById(
                CustomerGroup,
                group_id,
                data,
                request=request,
                tenant_config=True,
            )
            if updated is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Customer group not found.")
            return successResponse("Customer group updated successfully.", data=updated)

    @staticmethod
    def delete(data, request):
        ids = data.get("ids")
        if not isinstance(ids, list):
            ids = [ids]
        assigned = commonQuery.branchScopedQueryset(
            Customer,
            {"group_id__in": ids, "status": 0},
            request,
        ).count()
        if assigned > 0:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to delete a group to which customers are still assigned.")
        count = commonQuery.softDeleteById(
            CustomerGroup,
            ids,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer group not found.")
        return successResponse("Customer groups deleted successfully.")

    @staticmethod
    def updateStatus(data, request):
        status = data.get("status")
        count = commonQuery.updateStatusById(
            CustomerGroup,
            data.get("ids"),
            status,
            request=request,
            tenant_config=True,
        )
        if count == 0:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer group not found.")
        return successResponse(
            "Customer group status updated successfully.",
            data={"updated_count": count, "status": status},
        )

    @staticmethod
    def getCustomers(group_id, request):
        group = commonQuery.findOneRecord(CustomerGroup, group_id, request=request, tenant_config=True)
        if group is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Customer group not found.")
        customers = commonQuery.findAllRecords(
            Customer,
            {"group_id": group_id},
            {
                "attributes": ["id", "first_name", "last_name", "phone", "email", "group_id", "status"],
                "order": ["first_name", "last_name"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Customer group customers retrieved successfully.", data=customers)

    @staticmethod
    def transferCustomers(data, request):
        from_group_id = data.get("from") or data.get("from_group_id")
        to_group_id = data.get("to") or data.get("to_group_id")
        ids = data.get("ids")
        if from_group_id == to_group_id:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Unable to transfer customers to the same account.")
        if ids is None:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "No customer identifier has been provided to proceed to the transfer.")
        validateTenantRelationId(CustomerGroup, from_group_id, request=request, label="Source customer group", tenant_config=True)
        validateTenantRelationId(CustomerGroup, to_group_id, request=request, label="Destination customer group", tenant_config=True)
        target_group = commonQuery.branchScopedQueryset(
            CustomerGroup,
            {"id": to_group_id, "status__in": [0, 1]},
            request,
        ).first()

        queryset = commonQuery.branchScopedQueryset(
            Customer,
            {"group_id": from_group_id, "status": 0},
            request,
        )
        if ids == "*":
            message = f"All the customers has been transferred to the new group {target_group.name}."
        elif isinstance(ids, list):
            message = f"The categories has been transferred to the group {target_group.name}."
        else:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "No customer identifier has been provided to proceed to the transfer.")

        if ids != "*":
            if not isinstance(ids, list):
                ids = [ids]
            queryset = queryset.filter(id__in=ids)
        updated_count = queryset.update(group_id=to_group_id)
        return successResponse(
            message,
            data={"updated_count": updated_count},
        )
