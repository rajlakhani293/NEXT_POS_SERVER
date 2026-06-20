# type: ignore
from decimal import Decimal
from types import SimpleNamespace

from django.db import transaction
from django.utils.text import slugify

from apps.accounts.models import Role, User, UserRoleRelation
from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import validateTenantRelationId
from apps.common.responses import successResponse
from apps.customers.models import CUSTOMER_ROLE_CODE, Customer, CustomerAccountHistory, CustomerAddress, CustomerGroup
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
    while User.objects.filter(username=username).exists():
        counter += 1
        username = f"{base}-{counter}"
    return username


def getOrCreateCustomerRole(request):
    company_id = getattr(request.user, "company_id", None)
    branch_id = getattr(request.user, "branch_id", None)
    role = Role.objects.filter(company_id=company_id, branch_id=branch_id, namespace=CUSTOMER_ROLE_CODE).first()
    if role:
        return role
    return Role.objects.create(
        company_id=company_id,
        branch_id=branch_id,
        user_id=getattr(request.user, "id", None),
        name="Store Customer",
        namespace=CUSTOMER_ROLE_CODE,
        locked=True,
        description="Customer account used for POS orders, rewards, coupons, and account history.",
    )


def assignCustomerRole(user, role):
    relation, _created = UserRoleRelation.objects.get_or_create(
        user_id=user.id,
        role_id=role.id,
        defaults={
            "company_id": user.company_id,
            "branch_id": user.branch_id,
            "status": 0,
        },
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
                address_data[address_type][field] = customer_data.pop(source_key) or None
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
        for item in result.get("items", []):
            item["name"] = f"{item.get('first_name') or ''} {item.get('last_name') or ''}".strip()
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
        count = commonQuery.softDeleteById(
            Customer,
            data.get("ids"),
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


class CustomerAccountService:
    DEDUCT_OPERATIONS = ["deduct", "payment"]
    ADD_OPERATIONS = ["add", "refund"]
    OPERATIONS = DEDUCT_OPERATIONS + ADD_OPERATIONS

    @staticmethod
    def requestFromJob(job):
        user = User.objects.select_related("company", "branch").get(id=job.user_id)
        return SimpleNamespace(user=user)

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
                Customer.objects.select_for_update()
                .filter(
                    id=customer_id,
                    company_id=getattr(request.user, "company_id", None),
                    branch_id=getattr(request.user, "branch_id", None),
                )
                .first()
            )
            if customer is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Customer not found.")

            latest_history = (
                CustomerAccountHistory.objects.select_for_update()
                .filter(
                    customer_id=customer_id,
                    company_id=getattr(request.user, "company_id", None),
                    branch_id=getattr(request.user, "branch_id", None),
                    status=0,
                )
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
            OrderPayment.objects.select_related("sale_order")
            .filter(
                id=payment_id,
                company_id=getattr(request.user, "company_id", None),
                branch_id=getattr(request.user, "branch_id", None),
                status=0,
            )
            .first()
        )
        if payment is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Order payment not found.")
        if payment.identifier != "account-payment":
            return successResponse("Payment does not use customer account.", data={"skipped": True})
        sale_order = payment.sale_order
        if not sale_order.customer_id:
            raise api_error(400, ErrorCodes.BAD_REQUEST, "Customer is required for account payment.")

        existing = CustomerAccountHistory.objects.filter(
            customer_id=sale_order.customer_id,
            order_id=sale_order.id,
            operation="payment",
            amount=payment.value,
            company_id=getattr(request.user, "company_id", None),
            branch_id=getattr(request.user, "branch_id", None),
            status=0,
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
        count = commonQuery.softDeleteById(
            CustomerGroup,
            data.get("ids"),
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
