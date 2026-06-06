# type: ignore
from decimal import Decimal

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from apps.common.commonQuery import commonQuery
from apps.common.responses import successResponse
from apps.customers.models import Customer, CustomerCreditLedger
from apps.expenses.models import ExpenseEntry
from apps.inventory.models import StockLedger
from apps.purchases.models import PurchaseOrder, Supplier
from apps.sales.models import SaleOrder


def tenantFilter(request):
    return {
        "company_id": request.user.company_id,
        "branch_id": request.user.branch_id,
        "status__in": [0, 1],
    }


def dateFilter(field, data):
    filters = {}
    if not data:
        return filters
    if data.get("startDate"):
        filters[f"{field}__gte"] = data.get("startDate")
    if data.get("endDate"):
        filters[f"{field}__lte"] = data.get("endDate")
    return filters


class ReportService:
    @staticmethod
    def dashboardSummary(data, request):
        base = tenantFilter(request)
        sale_filters = {**base, **dateFilter("created_at", data)}
        expense_filters = {**base, **dateFilter("expense_date", data)}
        zero = Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))
        sales = SaleOrder.objects.filter(**sale_filters).aggregate(
            total_sales=Coalesce(Sum("total"), zero),
            total_paid=Coalesce(Sum("paid_amount"), zero),
            total_due=Coalesce(Sum("due_amount"), zero),
            order_count=Count("id"),
        )
        purchases = PurchaseOrder.objects.filter(**base).aggregate(
            total_purchase=Coalesce(Sum("total"), zero),
            total_purchase_due=Coalesce(Sum("total"), zero) - Coalesce(Sum("paid_amount"), zero),
            purchase_count=Count("id"),
        )
        expenses = ExpenseEntry.objects.filter(**expense_filters).aggregate(
            total_expense=Coalesce(Sum("amount"), zero),
            expense_count=Count("id"),
        )
        customers = Customer.objects.filter(**base).aggregate(
            total_customer_due=Coalesce(Sum("owed_amount"), zero),
            customer_count=Count("id"),
        )
        suppliers = Supplier.objects.filter(**base).aggregate(
            total_supplier_payable=Coalesce(Sum("payable_amount"), zero),
            supplier_count=Count("id"),
        )
        return successResponse(
            "Dashboard summary retrieved successfully.",
            data={
                "sales": sales,
                "purchases": purchases,
                "expenses": expenses,
                "customers": customers,
                "suppliers": suppliers,
            },
        )

    @staticmethod
    def customerDue(data, request):
        result = commonQuery.fetchPaginatedData(
            Customer,
            data,
            [["name", True, True], ["phone", True, True], ["code", True, True]],
            {"attributes": ["id", "name", "phone", "code", "owed_amount", "credit_limit_amount", "wallet_balance", "status"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Customer due report retrieved successfully.", data=result)

    @staticmethod
    def supplierPayable(data, request):
        result = commonQuery.fetchPaginatedData(
            Supplier,
            data,
            [["name", True, True], ["phone", True, True], ["code", True, True]],
            {"attributes": ["id", "name", "phone", "code", "payable_amount", "status"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Supplier payable report retrieved successfully.", data=result)

    @staticmethod
    def stockLedger(data, request):
        result = commonQuery.fetchPaginatedData(
            StockLedger,
            data,
            [["entry_type", True, True], ["reference_type", True, True], ["note", True, True]],
            {
                "attributes": [
                    "id",
                    "product_id",
                    "product__name",
                    "entry_type",
                    "quantity",
                    "unit_cost",
                    "balance_after",
                    "reference_type",
                    "reference_id",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Stock ledger report retrieved successfully.", data=result)

    @staticmethod
    def customerCreditLedger(data, request):
        result = commonQuery.fetchPaginatedData(
            CustomerCreditLedger,
            data,
            [["direction", True, True], ["reason", True, True], ["note", True, True]],
            {
                "attributes": [
                    "id",
                    "customer_id",
                    "customer__name",
                    "amount",
                    "direction",
                    "balance_after",
                    "reason",
                    "reference_type",
                    "reference_id",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Customer credit report retrieved successfully.", data=result)
