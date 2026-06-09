# type: ignore
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models.functions import TruncDate

from apps.common.commonQuery import commonQuery
from apps.common.helpers import jsonsafe
from apps.common.responses import successResponse
from apps.customers.models import Customer, CustomerCreditLedger
from apps.expenses.models import ExpenseEntry
from apps.inventory.models import StockLedger
from apps.purchases.models import PurchaseOrder, Supplier
from apps.registers.models import CashierShift
from apps.reports.models import DashboardDay, DashboardMonth
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
            total_paid=Coalesce(Sum("tendered_amount"), zero),
            total_due=Coalesce(Sum("due_amount"), zero),
            order_count=Count("id"),
            paid_orders=Count("id", filter=Q(payment_status="paid")),
            partially_paid_orders=Count("id", filter=Q(payment_status="partially_paid")),
            unpaid_orders=Count("id", filter=Q(payment_status="unpaid")),
            refunded_orders=Count("id", filter=Q(payment_status="refunded")),
            partially_refunded_orders=Count("id", filter=Q(payment_status="partially_refunded")),
            void_orders=Count("id", filter=Q(payment_status="void")),
            refund_total=Coalesce(Sum("total", filter=Q(payment_status__in=["refunded", "partially_refunded"])), zero),
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
        best_customers = list(
            SaleOrder.objects.filter(**sale_filters)
            .exclude(customer_id__isnull=True)
            .values("customer_id", "customer__name")
            .annotate(
                order_count=Count("id"),
                total_spent=Coalesce(Sum("total"), zero),
            )
            .order_by("-total_spent", "-order_count")[:5]
        )
        best_cashiers = list(
            SaleOrder.objects.filter(**sale_filters)
            .exclude(cashier_id__isnull=True)
            .values("cashier_id", "cashier__full_name")
            .annotate(
                order_count=Count("id"),
                total_sales=Coalesce(Sum("total"), zero),
            )
            .order_by("-total_sales", "-order_count")[:5]
        )
        recent_orders = list(
            SaleOrder.objects.filter(**sale_filters)
            .values(
                "id",
                "code",
                "customer__name",
                "cashier__full_name",
                "payment_status",
                "order_type",
                "total",
                "created_at",
            )
            .order_by("-created_at")[:8]
        )
        weekly_sales = list(
            SaleOrder.objects.filter(**base, created_at__gte=timezone.now() - timedelta(days=6))
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                total_sales=Coalesce(Sum("total"), zero),
                order_count=Count("id"),
            )
            .order_by("day")
        )
        shift = (
            CashierShift.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                shift_status="open",
                status__in=[0, 1],
            )
            .order_by("-opened_at")
            .values(
                "id",
                "register_id",
                "register__name",
                "cashier_id",
                "cashier__full_name",
                "opening_cash",
                "expected_cash",
                "total_sales_amount",
                "total_refund_amount",
                "total_cash_in",
                "total_cash_out",
                "opened_at",
            )
            .first()
        )
        return successResponse(
            "Dashboard summary retrieved successfully.",
            data={
                "sales": sales,
                "purchases": purchases,
                "expenses": expenses,
                "customers": customers,
                "suppliers": suppliers,
                "best_customers": best_customers,
                "best_cashiers": best_cashiers,
                "recent_orders": recent_orders,
                "weekly_sales": weekly_sales,
                "shift": shift,
            },
        )

    @staticmethod
    def refreshDashboardSnapshot(data, request):
        target_date = timezone.localdate()
        if data and data.get("date"):
            target_date = timezone.datetime.fromisoformat(str(data.get("date"))).date()
        start = timezone.make_aware(timezone.datetime.combine(target_date, timezone.datetime.min.time()))
        end = timezone.make_aware(timezone.datetime.combine(target_date, timezone.datetime.max.time()))

        summary_payload = ReportService.dashboardSummary({"startDate": start, "endDate": end}, request).data
        sales = summary_payload.get("sales", {})
        purchases = summary_payload.get("purchases", {})
        expenses = summary_payload.get("expenses", {})
        customers = summary_payload.get("customers", {})
        suppliers = summary_payload.get("suppliers", {})

        defaults = {
            "total_sales": sales.get("total_sales") or 0,
            "total_purchases": purchases.get("total_purchase") or 0,
            "total_expenses": expenses.get("total_expense") or 0,
            "total_customer_due": customers.get("total_customer_due") or 0,
            "total_supplier_payable": suppliers.get("total_supplier_payable") or 0,
            "order_count": sales.get("order_count") or 0,
            "purchase_count": purchases.get("purchase_count") or 0,
            "expense_count": expenses.get("expense_count") or 0,
            "summary": jsonsafe(summary_payload),
        }
        day, _ = DashboardDay.objects.update_or_create(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            dashboard_date=target_date,
            defaults=defaults,
        )
        DashboardMonth.objects.update_or_create(
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
            year=target_date.year,
            month=target_date.month,
            defaults=defaults,
        )
        return successResponse("Dashboard snapshot refreshed successfully.", data=jsonsafe({"id": day.id, **defaults}))

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
