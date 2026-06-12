# type: ignore
from django.db import transaction

from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import buildCode, validateTenantRelationId
from apps.common.responses import successResponse
from apps.customers.models import Customer, CustomerAddress, CustomerCreditLedger, CustomerGroup
from apps.organizations.models import StateMaster
from apps.rewards.models import RewardSystem


ADDRESS_FIELDS = ["address_line_1", "pincode", "city", "state_id"]
ADDRESS_TYPES = ["billing", "shipping"]


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

    addresses = {}
    for address_type in ADDRESS_TYPES:
        addresses[address_type] = commonQuery.findOneRecord(
            CustomerAddress,
            {"customer_id": customer_data["id"], "address_type": address_type},
            request=request,
            tenant_config=True,
        )
    customer_data["addresses"] = addresses
    customer_data["address"] = addresses.get("billing")
    return customer_data


def validateAddressState(address_data, request):
    state_id = address_data.get("state_id")
    if not state_id:
        return
    validateTenantRelationId(
        StateMaster,
        state_id,
        request=request,
        label="State",
        tenant_config={},
    )


def upsertCustomerAddress(customer_id, address_type, address_data, request):
    if not any(value for value in address_data.values()):
        return None
    validateAddressState(address_data, request)

    existing = commonQuery.findOneRecord(
        CustomerAddress,
        {"customer_id": customer_id, "address_type": address_type},
        request=request,
        tenant_config=True,
    )
    payload = {
        **address_data,
        "customer_id": customer_id,
        "address_type": address_type,
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

            customer_data["code"] = buildCode(
                Customer,
                customer_data.get("name"),
                customer_data.get("code"),
                request,
            )
            if not customer_data.get("owed_amount"):
                customer_data["owed_amount"] = customer_data.get("opening_balance") or 0
            customer = commonQuery.createRecord(
                Customer,
                customer_data,
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
            ["name", True, True],
            ["phone", True, True],
            ["email", True, True],
            ["code", True, True],
        ]
        options = {
            "attributes": [
                "id",
                "name",
                "phone",
                "email",
                "code",
                "customer_type",
                "company_name",
                "gst_number",
                "opening_balance",
                "credit_limit_amount",
                "owed_amount",
                "wallet_balance",
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
        return successResponse("Customers retrieved successfully.", data=result)

    @staticmethod
    def dropdownList(request):
        customers = commonQuery.findAllRecords(
            Customer,
            {},
            {
                "attributes": ["id", "name", "phone"],
                "order": ["name"],
            },
            request=request,
            tenant_config=True,
        )
        data = [
            {
                "id": customer["id"],
                "name": customer.get("name")
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
            {"attributes": ["id", "name", "code"], "order": ["name"]},
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

            if "code" in customer_data:
                customer_data["code"] = buildCode(
                    Customer,
                    customer_data.get("name") or customer.get("name"),
                    customer_data.get("code"),
                    request,
                    exclude_id=customer_id,
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
                CustomerCreditLedger,
                {
                    "customer_id": customer_id,
                    "amount": amount,
                    "direction": direction,
                    "balance_after": balance_after,
                    "reason": data.get("reason") or "adjustment",
                    "reference_type": "manual_adjustment",
                    "note": data.get("note") or "",
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
            CustomerCreditLedger,
            data,
            [["direction", True, True], ["reason", True, True], ["note", True, True]],
            {
                "attributes": [
                    "id",
                    "customer_id",
                    "amount",
                    "direction",
                    "balance_after",
                    "reason",
                    "reference_type",
                    "reference_id",
                    "note",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
            custom_where={"customer_id": customer_id},
        )
        return successResponse("Customer credit ledger retrieved successfully.", data=result)


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

            data["code"] = buildCode(
                CustomerGroup,
                data.get("name"),
                data.get("code"),
                request,
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
        fieldConfig = [["name", True, True], ["code", True, True]]
        options = {
            "attributes": [
                "id",
                "name",
                "code",
                "description",
                "credit_limit",
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

            if "code" in data:
                data["code"] = buildCode(
                    CustomerGroup,
                    data.get("name") or group.get("name"),
                    data.get("code"),
                    request,
                    exclude_id=group_id,
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
