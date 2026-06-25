# type: ignore
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, FloatField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models.functions import TruncDate

from apps.common.commonQuery import commonQuery
from apps.common.error_codes import ErrorCodes
from apps.common.exceptions import api_error
from apps.common.helpers import jsonsafe
from apps.common.responses import successResponse
from apps.accounting.models import TransactionAccount, TransactionHistory
from apps.accounts.models import Role
from apps.catalog.models import ProductHistory, ProductHistoryCombined, ProductUnitQuantity
from apps.customers.models import Customer, CustomerAccountHistory
from apps.purchases.models import Procurement, Provider
from apps.reports.models import DashboardDay, DashboardMonth, DashboardWeek
from apps.sales.models import OrderPayment, OrdersProduct, Order
from apps.settings.services import NotificationService


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


def paginatedResponse(queryset, data):
    data = data or {}
    page = int(data.get("page") or 1)
    limit = int(data.get("limit") or 10)
    offset = (page - 1) * limit
    total = queryset.count()
    rows = list(queryset[offset : offset + limit])
    return {
        "items": jsonsafe(rows),
        "total": total,
        "totals": {},
        "currentPage": page,
        "pageSize": limit,
        "totalPages": (total + (limit - 1)) // (limit or 1),
        "hasNextPage": (offset + limit) < total,
        "hasPreviousPage": page > 1,
        "appliedFilters": data,
    }


def parseReportDate(value=None):
    if not value:
        return timezone.localdate()
    if hasattr(value, "date"):
        return timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    return timezone.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


class ReportService:
    ACCOUNT_CATEGORY_LABELS = {
        "assets": "Assets",
        "liabilities": "Liabilities",
        "revenues": "Revenues",
        "expenses": "Expenses",
    }
    COMBINED_PROCURED_ACTIONS = {
        ProductHistory.ACTION_ADDED,
        ProductHistory.ACTION_STOCKED,
        ProductHistory.ACTION_ADJUSTMENT_RETURN,
        ProductHistory.ACTION_CONVERT_IN,
        ProductHistory.ACTION_RETURNED,
        ProductHistory.ACTION_TRANSFER_IN,
        ProductHistory.ACTION_TRANSFER_CANCELED,
        ProductHistory.ACTION_TRANSFER_REJECTED,
    }
    COMBINED_DEFECTIVE_ACTIONS = {
        ProductHistory.ACTION_DELETED,
        ProductHistory.ACTION_LOST,
        ProductHistory.ACTION_REMOVED,
        ProductHistory.ACTION_DEFECTIVE,
    }

    @staticmethod
    def requestFromJob(job):
        from apps.common.helpers import requestFromJobUser

        return requestFromJobUser(job)

    @staticmethod
    def dashboardSummary(data, request):
        base = tenantFilter(request)
        sale_filters = {**base, **dateFilter("created_at", data)}
        zero = Value(Decimal("0"), output_field=DecimalField(max_digits=18, decimal_places=5))
        zero_float = Value(0.0, output_field=FloatField())
        sales = commonQuery.scopedQueryset(Order, sale_filters, request, tenant_config={}).aggregate(
            total_sales=Coalesce(Sum("total"), zero),
            total_paid=Coalesce(Sum("tendered_amount"), zero),
            total_due=Coalesce(Sum("total", filter=Q(payment_status__in=["unpaid", "partially_paid", "due", "partially_due"])), zero),
            order_count=Count("id"),
            paid_orders=Count("id", filter=Q(payment_status="paid")),
            partially_paid_orders=Count("id", filter=Q(payment_status="partially_paid")),
            unpaid_orders=Count("id", filter=Q(payment_status="unpaid")),
            refunded_orders=Count("id", filter=Q(payment_status="refunded")),
            partially_refunded_orders=Count("id", filter=Q(payment_status="partially_refunded")),
            void_orders=Count("id", filter=Q(payment_status="order_void")),
            refund_total=Coalesce(Sum("total", filter=Q(payment_status__in=["refunded", "partially_refunded"])), zero),
            tax_total=Coalesce(Sum("tax_amount"), zero),
            total_discount=Coalesce(Sum("discount_amount"), zero),
        )
        purchases = commonQuery.scopedQueryset(Procurement, base, request, tenant_config={}).aggregate(
            total_purchase=Coalesce(Sum("value"), zero_float, output_field=FloatField()),
            total_purchase_due=Coalesce(Sum("value", filter=Q(payment_status="unpaid")), zero_float, output_field=FloatField()),
            purchase_count=Count("id"),
        )
        expenses = {
            "total_expense": Decimal("0"),
            "expense_count": 0,
        }
        customers = commonQuery.scopedQueryset(Customer, base, request, tenant_config={}).aggregate(
            total_customer_due=Coalesce(Sum("owed_amount"), zero),
            customer_count=Count("id"),
        )
        suppliers = commonQuery.scopedQueryset(Provider, base, request, tenant_config={}).aggregate(
            total_supplier_payable=Coalesce(Sum("amount_due"), zero_float, output_field=FloatField()),
            supplier_count=Count("id"),
        )
        best_customers = list(
            commonQuery.scopedQueryset(Order, sale_filters, request, tenant_config={})
            .exclude(customer_id__isnull=True)
            .values("customer_id", "customer__full_name")
            .annotate(
                order_count=Count("id"),
                total_spent=Coalesce(Sum("total"), zero),
            )
            .order_by("-total_spent", "-order_count")[:5]
        )
        best_cashiers = list(
            commonQuery.scopedQueryset(Order, sale_filters, request, tenant_config={})
            .exclude(user_id__isnull=True)
            .values("user_id", "user__full_name")
            .annotate(
                order_count=Count("id"),
                total_sales=Coalesce(Sum("total"), zero),
            )
            .order_by("-total_sales", "-order_count")[:5]
        )
        recent_orders = list(
            commonQuery.scopedQueryset(Order, sale_filters, request, tenant_config={})
            .values(
                "id",
                "code",
                "customer__full_name",
                "user__full_name",
                "payment_status",
                "order_type",
                "total",
                "created_at",
            )
            .order_by("-created_at")[:8]
        )
        weekly_sales = list(
            commonQuery.scopedQueryset(
                Order,
                {**base, "created_at__gte": timezone.now() - timedelta(days=6)},
                request,
                tenant_config={},
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                total_sales=Coalesce(Sum("total"), zero),
                order_count=Count("id"),
            )
            .order_by("day")
        )
        prev_weekly_sales = list(
            commonQuery.scopedQueryset(
                Order,
                {
                    **base,
                    "created_at__gte": timezone.now() - timedelta(days=13),
                    "created_at__lt": timezone.now() - timedelta(days=6),
                },
                request,
                tenant_config={},
            )
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                total_sales=Coalesce(Sum("total"), zero),
                order_count=Count("id"),
            )
            .order_by("day")
        )

        # Get active shift
        from apps.registers.models import Register, RegistersHistory

        register = commonQuery.findOneInstance(
            Register,
            {"used_by_id": request.user.id, "register_status": Register.STATUS_OPENED},
            request=request,
            tenant_config=True,
        )
        shift_data = None
        if register:
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

            entries_qs = commonQuery.branchScopedQueryset(
                RegistersHistory,
                {
                    "register_id": register.id,
                    "created_at__gte": opened_at,
                },
                request,
            ).exclude(status=2)

            sales_collected = entries_qs.filter(entry_type=RegistersHistory.ACTION_ORDER_PAYMENT).aggregate(total=Sum("amount"))["total"] or 0
            refund_out = entries_qs.filter(entry_type=RegistersHistory.ACTION_REFUND).aggregate(total=Sum("amount"))["total"] or 0

            shift_data = {
                "id": register.id,
                "register_id": register.id,
                "register__name": register.name,
                "cashier__full_name": request.user.full_name or request.user.username,
                "opened_at": opened_at.isoformat() if opened_at else None,
                "opening_cash": float(opening_cash),
                "expected_cash": float(register.balance),
                "total_sales_amount": float(sales_collected),
                "total_refund_amount": float(refund_out),
            }

        # Cashier profile stats
        today_date = timezone.localdate()
        today_start = timezone.make_aware(timezone.datetime.combine(today_date, timezone.datetime.min.time()))
        today_end = timezone.make_aware(timezone.datetime.combine(today_date, timezone.datetime.max.time()))

        user_orders = commonQuery.scopedQueryset(Order, base, request, tenant_config={}).filter(user_id=request.user.id)
        user_orders_today = user_orders.filter(created_at__range=(today_start, today_end))

        cashier_metrics = user_orders.aggregate(
            total_orders=Count("id"),
            total_sales_amount=Coalesce(Sum("total", filter=Q(payment_status__in=["paid", "partially_paid"])), zero),
            total_refunds_amount=Coalesce(Sum("total", filter=Q(payment_status__in=["refunded", "partially_refunded"])), zero),
        )

        cashier_metrics_today = user_orders_today.aggregate(
            today_orders=Count("id"),
            today_sales_amount=Coalesce(Sum("total", filter=Q(payment_status__in=["paid", "partially_paid"])), zero),
            today_refunds_amount=Coalesce(Sum("total", filter=Q(payment_status__in=["refunded", "partially_refunded"])), zero),
        )

        user_customers = commonQuery.scopedQueryset(Customer, base, request, tenant_config={})
        user_customers_today = user_customers.filter(date_joined__range=(today_start, today_end))

        cashier_stats = {
            "cashier_name": request.user.full_name or request.user.username,
            "member_since": request.user.date_joined.strftime("%Y-%m-%d") if hasattr(request.user, "date_joined") and request.user.date_joined else "",
            "total_orders": cashier_metrics["total_orders"],
            "today_orders": cashier_metrics_today["today_orders"],
            "total_sales": float(cashier_metrics["total_sales_amount"]),
            "today_sales": float(cashier_metrics_today["today_sales_amount"]),
            "total_refunds": float(cashier_metrics["total_refunds_amount"]),
            "today_refunds": float(cashier_metrics_today["today_refunds_amount"]),
            "total_customers": user_customers.count(),
            "today_customers": user_customers_today.count(),
        }

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
                "prev_weekly_sales": prev_weekly_sales,
                "shift": shift_data,
                "cashier_stats": cashier_stats,
            },
        )

    @staticmethod
    def annualReport(data, request):
        from django.db.models.functions import TruncMonth
        from apps.accounting.models import TransactionHistory

        year = int((data or {}).get("year") or timezone.localdate().year)
        base = tenantFilter(request)
        zero = Value(Decimal("0"), output_field=DecimalField(max_digits=18, decimal_places=5))

        # Sales per month
        sales_qs = (
            commonQuery.scopedQueryset(Order, base, request, tenant_config={})
            .filter(created_at__year=year)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(
                total_sales=Coalesce(Sum("total"), zero),
                total_taxes=Coalesce(Sum("tax_amount"), zero),
                total_discounts=Coalesce(Sum("discount_amount"), zero),
                order_count=Count("id"),
            )
            .order_by("month")
        )

        # Expenses per month via transaction history (debit side)
        expenses_qs = (
            TransactionHistory.objects.filter(
                company_id=request.user.company_id,
                branch_id=request.user.branch_id,
                created_at__year=year,
                action_type="debit",
            )
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(total_expenses=Coalesce(Sum("amount"), zero))
            .order_by("month")
        )

        MONTH_NAMES = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]

        # Build full 12-month skeleton
        months: dict = {i: {"month": i, "label": MONTH_NAMES[i - 1], "total_sales": Decimal("0"), "total_taxes": Decimal("0"), "total_discounts": Decimal("0"), "total_expenses": Decimal("0"), "net_income": Decimal("0"), "order_count": 0} for i in range(1, 13)}

        for row in sales_qs:
            m = row["month"].month
            months[m]["total_sales"] = row["total_sales"]
            months[m]["total_taxes"] = row["total_taxes"]
            months[m]["total_discounts"] = row["total_discounts"]
            months[m]["order_count"] = row["order_count"]

        for row in expenses_qs:
            m = row["month"].month
            months[m]["total_expenses"] = row["total_expenses"]

        for m in months.values():
            m["net_income"] = m["total_sales"] - m["total_expenses"]

        return successResponse(
            "Annual report retrieved successfully.",
            data={
                "year": year,
                "months": list(months.values()),
                "totals": {
                    "total_sales": sum(m["total_sales"] for m in months.values()),
                    "total_taxes": sum(m["total_taxes"] for m in months.values()),
                    "total_expenses": sum(m["total_expenses"] for m in months.values()),
                    "net_income": sum(m["net_income"] for m in months.values()),
                },
            },
        )

    @staticmethod
    def refreshDashboardSnapshot(data, request):

        target_date = timezone.localdate()
        if data and data.get("date"):
            target_date = timezone.datetime.fromisoformat(str(data.get("date"))).date()
        start = timezone.make_aware(timezone.datetime.combine(target_date, timezone.datetime.min.time()))
        end = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.max.time()).replace(microsecond=0)
        )

        summary_payload = ReportService.dashboardSummary({"startDate": start, "endDate": end}, request).data
        sales = summary_payload.get("sales", {})
        purchases = summary_payload.get("purchases", {})
        expenses = summary_payload.get("expenses", {})
        customers = summary_payload.get("customers", {})
        suppliers = summary_payload.get("suppliers", {})

        total_paid = sales.get("total_paid") or 0
        total_due = sales.get("total_due") or 0
        paid_count = sales.get("paid_orders") or 0
        unpaid_count = sales.get("unpaid_orders") or 0
        partial_count = sales.get("partially_paid_orders") or 0
        income = sales.get("total_sales") or 0
        tax_total = sales.get("tax_total") or 0
        discounts = sales.get("total_discount") or 0
        expense_total = expenses.get("total_expense") or 0
        defaults = {
            "day_paid_orders": total_paid,
            "total_paid_orders": total_paid,
            "day_paid_orders_count": paid_count,
            "total_paid_orders_count": paid_count,
            "day_unpaid_orders": total_due,
            "total_unpaid_orders": total_due,
            "day_unpaid_orders_count": unpaid_count,
            "total_unpaid_orders_count": unpaid_count,
            "day_partially_paid_orders": total_due if partial_count else 0,
            "total_partially_paid_orders": total_due if partial_count else 0,
            "day_partially_paid_orders_count": partial_count,
            "total_partially_paid_orders_count": partial_count,
            "day_income": income,
            "total_income": income,
            "day_discounts": discounts,
            "total_discounts": discounts,
            "day_taxes": tax_total,
            "total_taxes": tax_total,
            "day_expenses": expense_total,
            "total_expenses": expense_total,
        }
        day, _ = commonQuery.updateOrCreateInstance(
            DashboardDay,
            {
                "range_starts": start,
                "range_ends": end,
                "day_of_year": target_date.timetuple().tm_yday,
            },
            defaults=defaults,
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        week_start = (start - timedelta(days=target_date.weekday())).replace(microsecond=0)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        commonQuery.updateOrCreateInstance(
            DashboardWeek,
            {
                "range_starts": week_start,
                "range_ends": week_end,
                "week_number": int(target_date.strftime("%U")),
            },
            defaults={
                "total_gross_income": income,
                "total_taxes": tax_total,
                "total_expenses": expense_total,
                "total_net_income": income - tax_total - expense_total,
            },
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        month_start = timezone.make_aware(timezone.datetime(target_date.year, target_date.month, 1))
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = (next_month - timedelta(seconds=1)).replace(microsecond=0)
        commonQuery.updateOrCreateInstance(
            DashboardMonth,
            {
                "range_starts": month_start,
                "range_ends": month_end,
                "month_of_year": target_date.month,
            },
            defaults={
                "month_paid_orders": total_paid,
                "total_paid_orders": total_paid,
                "month_paid_orders_count": paid_count,
                "total_paid_orders_count": paid_count,
                "month_unpaid_orders": total_due,
                "total_unpaid_orders": total_due,
                "month_unpaid_orders_count": unpaid_count,
                "total_unpaid_orders_count": unpaid_count,
                "month_partially_paid_orders": total_due if partial_count else 0,
                "total_partially_paid_orders": total_due if partial_count else 0,
                "month_partially_paid_orders_count": partial_count,
                "total_partially_paid_orders_count": partial_count,
                "month_income": income,
                "total_income": income,
                "month_discounts": discounts,
                "total_discounts": discounts,
                "month_taxes": tax_total,
                "total_taxes": tax_total,
                "month_expenses": expense_total,
                "total_expenses": expense_total,
            },
            request=request,
            tenant_config={"company_id": True, "branch_id": True},
        )
        return successResponse("Dashboard snapshot refreshed successfully.", data=jsonsafe({"id": day.id, **defaults}))

    @staticmethod
    def recomputeDashboardRange(data, request):
        from apps.accounting.services import AccountingService

        start_date = parseReportDate((data or {}).get("from_date") or (data or {}).get("startDate"))
        end_date = parseReportDate((data or {}).get("to_date") or (data or {}).get("endDate"))
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        commonQuery.branchScopedQueryset(
            DashboardDay,
            {"range_starts__date__gte": start_date, "range_starts__date__lte": end_date},
            request,
        ).delete()
        commonQuery.branchScopedQueryset(
            DashboardWeek,
            {"range_starts__date__lte": end_date, "range_ends__date__gte": start_date},
            request,
        ).delete()
        commonQuery.branchScopedQueryset(
            DashboardMonth,
            {"range_starts__date__lte": end_date, "range_ends__date__gte": start_date},
            request,
        ).delete()

        current_date = start_date
        refreshed_days = 0
        while current_date <= end_date:
            ReportService.refreshDashboardSnapshot({"date": current_date.isoformat()}, request)
            refreshed_days += 1
            current_date += timedelta(days=1)

        AccountingService.recomputeBalances(start_date.isoformat(), end_date.isoformat(), request)
        return successResponse(
            "Dashboard reports recomputed successfully.",
            data={
                "from_date": start_date,
                "to_date": end_date,
                "refreshed_days": refreshed_days,
            },
        )

    @staticmethod
    def customerDue(data, request):
        result = commonQuery.fetchPaginatedData(
            Customer,
            data,
            [["first_name", True, True], ["last_name", True, True], ["phone", True, True]],
            {"attributes": ["id", "first_name", "last_name", "phone", "owed_amount", "credit_limit_amount", "account_amount", "status"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Customer due report retrieved successfully.", data=result)

    @staticmethod
    def supplierPayable(data, request):
        result = commonQuery.fetchPaginatedData(
            Provider,
            data,
            [["first_name", True, True], ["last_name", True, True], ["phone", True, True], ["email", True, True]],
            {"attributes": ["id", "first_name", "last_name", "phone", "email", "amount_due", "amount_paid", "status"]},
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["name"] = " ".join([part for part in [item.get("first_name"), item.get("last_name")] if part]).strip()
            item["payable_amount"] = item.get("amount_due")
        return successResponse("Provider payable report retrieved successfully.", data=result)

    @staticmethod
    def stockLedger(data, request):
        result = commonQuery.fetchPaginatedData(
            ProductHistory,
            data,
            [["operation_type", True, True], ["description", True, True]],
            {
                "attributes": [
                    "id",
                    "product_id",
                    "product__name",
                    "operation_type",
                    "quantity",
                    "unit_price",
                    "after_quantity",
                    "order_id",
                    "procurement_id",
                    "description",
                    "created_at",
                    "status",
                ],
            },
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["entry_type"] = item.pop("operation_type", None)
            item["unit_cost"] = item.pop("unit_price", None)
            item["balance_after"] = item.pop("after_quantity", None)
            item["reference_type"] = "sale_order" if item.get("order_id") else "purchase_order" if item.get("procurement_id") else "product_history"
            item["reference_id"] = item.get("order_id") or item.get("procurement_id")
        return successResponse("Stock ledger report retrieved successfully.", data=result)

    @staticmethod
    def customerCreditLedger(data, request):
        result = commonQuery.fetchPaginatedData(
            CustomerAccountHistory,
            data,
            [["operation", True, True], ["description", True, True]],
            {
                "attributes": [
                    "id",
                    "customer_id",
                    "customer__first_name",
                    "customer__last_name",
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
        )
        return successResponse("Customer credit report retrieved successfully.", data=result)

    @staticmethod
    def saleReport(data, request):
        result = commonQuery.fetchPaginatedData(
            Order,
            data,
            [["code", True, True], ["customer__full_name", True, True], ["user__full_name", True, True], ["payment_status", True, True]],
            {
                "attributes": [
                    "id",
                    "code",
                    "customer__full_name",
                    "user__full_name",
                    "order_type",
                    "payment_status",
                    "subtotal",
                    "discount_amount",
                    "tax_amount",
                    "total",
                    "tendered_amount",
                    "created_at",
                    "status",
                ],
                "sumField": ["total", "tendered_amount"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Sale report retrieved successfully.", data=result)

    @staticmethod
    def soldStockReport(data, request):
        field_config = [["product__name", True, True], ["sale_order__code", True, True]]
        result = commonQuery.fetchPaginatedData(
            OrdersProduct,
            data,
            field_config,
            {
                "attributes": [
                    "id",
                    "sale_order_id",
                    "sale_order__code",
                    "product_id",
                    "product__name",
                    "quantity",
                    "unit_price",
                    "discount_amount",
                    "tax_amount",
                    "total",
                    "cost_price",
                    "created_at",
                    "status",
                ],
                "sumField": ["quantity", "total"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Sold stock report retrieved successfully.", data=result)

    @staticmethod
    def profitReport(data, request):
        base = tenantFilter(request)
        filters = {**base, **dateFilter("created_at", data)}
        zero = Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))
        queryset = commonQuery.scopedQueryset(OrdersProduct, filters, request, tenant_config={}).annotate(
            cost_total=ExpressionWrapper(
                F("quantity") * F("cost_price"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            profit_amount=ExpressionWrapper(
                F("total") - (F("quantity") * F("cost_price")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        search = (data or {}).get("search")
        if search:
            queryset = queryset.filter(Q(product__name__icontains=search) | Q(sale_order__code__icontains=search))
        summary = queryset.aggregate(
            total_sales=Coalesce(Sum("total"), zero),
            total_cost=Coalesce(Sum("cost_total"), zero),
            total_profit=Coalesce(Sum("profit_amount"), zero),
            item_count=Count("id"),
        )
        rows = queryset.values(
            "id",
            "sale_order_id",
            "sale_order__code",
            "product_id",
            "product__name",
            "quantity",
            "total",
            "cost_total",
            "profit_amount",
            "created_at",
        ).order_by("-created_at", "-id")
        result = paginatedResponse(rows, data)
        result["totals"] = summary
        return successResponse("Profit report retrieved successfully.", data=result)

    @staticmethod
    def paymentTypesReport(data, request):
        result = commonQuery.fetchPaginatedData(
            OrderPayment,
            data,
            [["identifier", True, True], ["sale_order__code", True, True]],
            {
                "attributes": [
                    "id",
                    "sale_order_id",
                    "sale_order__code",
                    "identifier",
                    "value",
                    "created_at",
                    "status",
                ],
                "sumField": ["value"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Payment types report retrieved successfully.", data=result)

    @staticmethod
    def accountSummaryReport(data, request):
        data = data or {}
        history_filters = {
            "histories__company_id": request.user.company_id,
            "histories__branch_id": request.user.branch_id,
            "histories__status__in": [0, 1],
            **dateFilter("histories__created_at", data),
        }
        accounts = (
            commonQuery.scopedQueryset(TransactionAccount, tenantFilter(request), request, tenant_config={})
            .annotate(
                debits=Coalesce(
                    Sum("histories__value", filter=Q(histories__operation=TransactionHistory.OPERATION_DEBIT, **history_filters)),
                    Value(Decimal("0"), output_field=DecimalField(max_digits=18, decimal_places=5)),
                ),
                credits=Coalesce(
                    Sum("histories__value", filter=Q(histories__operation=TransactionHistory.OPERATION_CREDIT, **history_filters)),
                    Value(Decimal("0"), output_field=DecimalField(max_digits=18, decimal_places=5)),
                ),
            )
            .values(
                "id",
                "name",
                "account",
                "category_identifier",
                "sub_category_id",
                "sub_category__name",
                "debits",
                "credits",
            )
            .order_by("category_identifier", "account", "name")
        )

        grouped = {}
        total_debits = Decimal("0")
        total_credits = Decimal("0")
        for account in accounts:
            category = account.get("category_identifier") or "uncategorized"
            grouped.setdefault(
                category,
                {
                    "name": ReportService.ACCOUNT_CATEGORY_LABELS.get(category, category.replace("_", " ").title()),
                    "transactions": [],
                    "debits": Decimal("0"),
                    "credits": Decimal("0"),
                },
            )
            grouped[category]["transactions"].append(account)
            grouped[category]["debits"] += account.get("debits") or Decimal("0")
            grouped[category]["credits"] += account.get("credits") or Decimal("0")
            total_debits += account.get("debits") or Decimal("0")
            total_credits += account.get("credits") or Decimal("0")

        return successResponse(
            "Account summary report retrieved successfully.",
            data=jsonsafe(
                {
                    "accounts": grouped,
                    "debits": total_debits,
                    "credits": total_credits,
                    "profit": total_credits - total_debits,
                }
            ),
        )

    @staticmethod
    def productsReport(data, request):
        queryset = commonQuery.scopedQueryset(ProductUnitQuantity, tenantFilter(request), request, tenant_config={}).annotate(
            sold_quantity=Coalesce(Sum("sale_items__quantity"), Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=3))),
            sold_amount=Coalesce(Sum("sale_items__total"), Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))),
        )
        search = (data or {}).get("search")
        if search:
            queryset = queryset.filter(Q(product__name__icontains=search) | Q(product__sku__icontains=search) | Q(product__barcode__icontains=search) | Q(barcode__icontains=search))
        rows = queryset.values(
            "id",
            "product_id",
            "product__name",
            "product__sku",
            "product__barcode",
            "product__product_type",
            "quantity",
            "low_quantity",
            "cogs",
            "sale_price",
            "sold_quantity",
            "sold_amount",
            "status",
        ).order_by("product__name")
        result = paginatedResponse(rows, data)
        for item in result["items"]:
            item["name"] = item.pop("product__name", None)
            item["sku"] = item.pop("product__sku", None)
            item["barcode"] = item.pop("product__barcode", None) or item.get("barcode")
            item["product_type"] = item.pop("product__product_type", None)
            item["current_stock"] = item.pop("quantity", 0)
            item["min_stock"] = item.pop("low_quantity", 0)
            item["purchase_price"] = item.pop("cogs", 0)
            item["selling_price"] = item.pop("sale_price", 0)
        return successResponse("Products report retrieved successfully.", data=result)

    @staticmethod
    def lowStockReport(data, request):
        queryset = commonQuery.scopedQueryset(
            ProductUnitQuantity,
            {
                **tenantFilter(request),
                "stock_alert_enabled": True,
                "quantity__lt": F("low_quantity"),
            },
            request,
            tenant_config={},
        ).values(
            "id",
            "product_id",
            "product__name",
            "product__sku",
            "product__barcode",
            "barcode",
            "quantity",
            "low_quantity",
            "cogs",
            "sale_price",
            "status",
        ).order_by("quantity", "product__name")
        search = (data or {}).get("search")
        if search:
            queryset = queryset.filter(Q(product__name__icontains=search) | Q(product__sku__icontains=search) | Q(product__barcode__icontains=search) | Q(barcode__icontains=search))
        result = paginatedResponse(queryset, data)
        for item in result["items"]:
            item["name"] = item.pop("product__name", None)
            item["sku"] = item.pop("product__sku", None)
            item["barcode"] = item.pop("product__barcode", None) or item.get("barcode")
            item["current_stock"] = item.pop("quantity", 0)
            item["min_stock"] = item.pop("low_quantity", 0)
            item["max_stock"] = None
            item["purchase_price"] = item.pop("cogs", 0)
            item["selling_price"] = item.pop("sale_price", 0)
        return successResponse("Low stock report retrieved successfully.", data=result)

    @staticmethod
    def detectLowStockProducts(data, request):
        low_stock_count = commonQuery.branchScopedQueryset(
            ProductUnitQuantity,
            {"status__in": [0, 1], "stock_alert_enabled": True, "low_quantity__gt": F("quantity")},
            request,
        ).count()
        if low_stock_count > 0:
            NotificationService.dispatchForRoleNamespaces(
                [Role.ADMIN, Role.STOREADMIN],
                title="Low Stock Alert",
                description=f"{low_stock_count} product(s) has low stock. Reorder those product(s) before it gets exhausted.",
                identifier="low-stock-products",
                url="/reports/low-stock",
                source="system",
                request=request,
            )
        return successResponse("Low stock products checked successfully.", data={"low_stock_count": low_stock_count})

    @staticmethod
    def enqueueLowStockDetection(data, request):
        from apps.settings.services import JobQueueService

        job = JobQueueService.enqueue("detect_low_stock_products", data or {}, request=request)
        return successResponse("Low stock detection queued successfully.", data={"job_id": job.id})

    @staticmethod
    def stockReport(data, request):
        queryset = commonQuery.scopedQueryset(ProductUnitQuantity, tenantFilter(request), request, tenant_config={})
        search = (data or {}).get("search")
        if search:
            queryset = queryset.filter(Q(product__name__icontains=search) | Q(product__sku__icontains=search) | Q(product__barcode__icontains=search) | Q(barcode__icontains=search))
        rows = queryset.values(
            "id",
            "product_id",
            "product__name",
            "product__sku",
            "product__barcode",
            "barcode",
            "product__product_type",
            "product__stock_management",
            "quantity",
            "low_quantity",
            "cogs",
            "sale_price",
            "status",
        ).order_by("product__name")
        result = paginatedResponse(rows, data)
        for item in result["items"]:
            item["name"] = item.pop("product__name", None)
            item["sku"] = item.pop("product__sku", None)
            item["barcode"] = item.pop("product__barcode", None) or item.get("barcode")
            item["product_type"] = item.pop("product__product_type", None)
            item["track_stock"] = item.pop("product__stock_management", None) != "disabled"
            item["current_stock"] = item.pop("quantity", 0)
            item["opening_stock"] = None
            item["min_stock"] = item.pop("low_quantity", 0)
            item["max_stock"] = None
            item["purchase_price"] = item.pop("cogs", 0)
            item["selling_price"] = item.pop("sale_price", 0)
        return successResponse("Stock report retrieved successfully.", data=result)

    @staticmethod
    def stockCombinedReport(data, request):
        data = data or {}
        report_date = parseReportDate(data.get("date"))

        queryset = commonQuery.scopedQueryset(
            ProductHistoryCombined,
            {**tenantFilter(request), "date": report_date},
            request,
            tenant_config={},
        )
        categories = data.get("categories") or data.get("category_ids") or []
        units = data.get("units") or data.get("unit_ids") or []
        if categories:
            queryset = queryset.filter(product__category_id__in=categories)
        if units:
            queryset = queryset.filter(unit_id__in=units)

        search = data.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(product__sku__icontains=search) | Q(product__barcode__icontains=search))

        rows = queryset.values(
            "id",
            "date",
            "product_id",
            "product__name",
            "product__sku",
            "product__barcode",
            "product__category_id",
            "product__category__name",
            "unit_id",
            "unit__name",
            "name",
            "initial_quantity",
            "procured_quantity",
            "sold_quantity",
            "defective_quantity",
            "final_quantity",
            "status",
        ).order_by("product__name", "unit__name")
        result = paginatedResponse(rows, data)
        result["date"] = report_date
        return successResponse("Stock combined report retrieved successfully.", data=result)

    @staticmethod
    def recomputeStockCombined(data, request):
        report_date = parseReportDate((data or {}).get("date"))
        start = timezone.make_aware(timezone.datetime.combine(report_date, timezone.datetime.min.time()))
        end = timezone.make_aware(timezone.datetime.combine(report_date, timezone.datetime.max.time()))
        unit_quantities = commonQuery.branchScopedQueryset(
            ProductUnitQuantity,
            {
                "product__stock_management": "enabled",
                "product__type": "materialized",
                "status__in": [0, 1],
            },
            request,
        ).select_related("product", "unit")
        updated_count = 0
        for unit_quantity in unit_quantities:
            previous = (
                commonQuery.branchScopedQueryset(
                    ProductHistoryCombined,
                    {
                        "product_id": unit_quantity.product_id,
                        "unit_id": unit_quantity.unit_id,
                        "date__lt": report_date,
                        "status__in": [0, 1],
                    },
                    request,
                )
                .order_by("-date")
                .first()
            )
            initial_quantity = previous.final_quantity if previous else 0
            histories = commonQuery.branchScopedQueryset(
                ProductHistory,
                {
                    "product_id": unit_quantity.product_id,
                    "unit_id": unit_quantity.unit_id,
                    "created_at__gte": start,
                    "created_at__lte": end,
                    "status__in": [0, 1],
                },
                request,
            )
            procured_quantity = histories.filter(operation_type__in=ReportService.COMBINED_PROCURED_ACTIONS).aggregate(
                total=Coalesce(Sum("quantity"), Value(0.0), output_field=FloatField())
            )["total"]
            sold_quantity = histories.filter(operation_type=ProductHistory.ACTION_SOLD).aggregate(
                total=Coalesce(Sum("quantity"), Value(0.0), output_field=FloatField())
            )["total"]
            defective_quantity = histories.filter(operation_type__in=ReportService.COMBINED_DEFECTIVE_ACTIONS).aggregate(
                total=Coalesce(Sum("quantity"), Value(0.0), output_field=FloatField())
            )["total"]
            final_quantity = Decimal(str(initial_quantity or 0)) + Decimal(str(procured_quantity or 0)) - Decimal(str(sold_quantity or 0)) - Decimal(str(defective_quantity or 0))
            commonQuery.updateOrCreateInstance(
                ProductHistoryCombined,
                {
                    "product_id": unit_quantity.product_id,
                    "unit_id": unit_quantity.unit_id,
                    "date": report_date,
                },
                defaults={
                    "user_id": request.user.id,
                    "name": unit_quantity.product.name,
                    "initial_quantity": initial_quantity or 0,
                    "procured_quantity": procured_quantity or 0,
                    "sold_quantity": sold_quantity or 0,
                    "defective_quantity": defective_quantity or 0,
                    "final_quantity": final_quantity,
                    "status": 0,
                },
                request=request,
                tenant_config=True,
            )
            updated_count += 1
        return successResponse("Stock combined report recomputed successfully.", data={"date": report_date, "updated_count": updated_count})

    @staticmethod
    def handleStockAdjustment(data, request):
        data = data or {}
        history = None
        if data.get("history_id") or data.get("product_history_id"):
            history = commonQuery.branchScopedQueryset(
                ProductHistory,
                {"id": data.get("history_id") or data.get("product_history_id")},
                request,
            ).exclude(status=2).first()
            if history is None:
                raise api_error(404, ErrorCodes.NOT_FOUND, "Product history not found.")
            report_date = parseReportDate(history.created_at)
        else:
            report_date = parseReportDate(data.get("date"))

        start = timezone.make_aware(timezone.datetime.combine(report_date, timezone.datetime.min.time()))
        end = timezone.make_aware(timezone.datetime.combine(report_date, timezone.datetime.max.time()))
        histories = commonQuery.branchScopedQueryset(
            ProductHistory,
            {
                "operation_type__in": ReportService.COMBINED_DEFECTIVE_ACTIONS,
                "created_at__gte": start,
                "created_at__lte": end,
                "status__in": [0, 1],
            },
            request,
        )
        day_wasted_goods_count = histories.aggregate(total=Coalesce(Sum("quantity"), Value(0.0), output_field=FloatField()))["total"] or 0
        day_wasted_goods = histories.aggregate(total=Coalesce(Sum("total_price"), Value(0.0), output_field=FloatField()))["total"] or 0

        ReportService.refreshDashboardSnapshot({"date": report_date.isoformat()}, request)
        day = commonQuery.branchScopedQueryset(
            DashboardDay,
            {"range_starts": start, "range_ends": end},
            request,
        ).first()
        if day is None:
            raise api_error(404, ErrorCodes.NOT_FOUND, "Dashboard day not found.")
        previous_day = commonQuery.branchScopedQueryset(
            DashboardDay,
            {"range_starts__lt": start},
            request,
        ).order_by("-range_starts").first()
        day.day_wasted_goods_count = Decimal(str(day_wasted_goods_count or 0))
        day.day_wasted_goods = Decimal(str(day_wasted_goods or 0))
        day.total_wasted_goods_count = Decimal(str(previous_day.total_wasted_goods_count if previous_day else 0)) + day.day_wasted_goods_count
        day.total_wasted_goods = Decimal(str(previous_day.total_wasted_goods if previous_day else 0)) + day.day_wasted_goods
        day.save(
            update_fields=[
                "day_wasted_goods_count",
                "day_wasted_goods",
                "total_wasted_goods_count",
                "total_wasted_goods",
                "updated_at",
            ]
        )
        return successResponse(
            "Stock adjustment report updated successfully.",
            data={
                "date": report_date,
                "day_wasted_goods_count": day.day_wasted_goods_count,
                "day_wasted_goods": day.day_wasted_goods,
            },
        )

    @staticmethod
    def enqueueStockCombinedRefresh(data, request):
        from apps.settings.services import JobQueueService

        job = JobQueueService.enqueue("ensure_combined_product_history", data or {}, request=request)
        return successResponse("Stock combined refresh queued successfully.", data={"job_id": job.id})

    @staticmethod
    def enqueueDashboardRecompute(data, request):
        from apps.settings.services import JobQueueService

        job = JobQueueService.enqueue("recompute_dashboard_reports", data or {}, request=request)
        return successResponse("Dashboard recompute queued successfully.", data={"job_id": job.id})

    @staticmethod
    def jobHandlers():
        return {
            "ensure_combined_product_history": lambda data, job: ReportService.recomputeStockCombined(data, ReportService.requestFromJob(job)),
            "initialize_daily_report": lambda data, job: ReportService.refreshDashboardSnapshot(data or {}, ReportService.requestFromJob(job)),
            "compute_day_report": lambda data, job: ReportService.refreshDashboardSnapshot(data or {}, ReportService.requestFromJob(job)),
            "refresh_report": lambda data, job: ReportService.refreshDashboardSnapshot(data or {}, ReportService.requestFromJob(job)),
            "compute_dashboard_day": lambda data, job: ReportService.refreshDashboardSnapshot(data or {}, ReportService.requestFromJob(job)),
            "compute_dashboard_month": lambda data, job: ReportService.refreshDashboardSnapshot(data or {}, ReportService.requestFromJob(job)),
            "detect_low_stock_products": lambda data, job: ReportService.detectLowStockProducts(data or {}, ReportService.requestFromJob(job)),
            "recompute_dashboard_reports": lambda data, job: ReportService.recomputeDashboardRange(data or {}, ReportService.requestFromJob(job)),
            "handle_stock_adjustment": lambda data, job: ReportService.handleStockAdjustment(data or {}, ReportService.requestFromJob(job)),
        }

    @staticmethod
    def cashierReport(data, request):
        queryset = commonQuery.scopedQueryset(
            Order,
            {**tenantFilter(request), **dateFilter("created_at", data)},
            request,
            tenant_config={},
        )
        if not request.user.is_superuser:
            queryset = queryset.filter(user_id=request.user.id)
        rows = queryset.values("user_id", "user__full_name").annotate(
            order_count=Count("id"),
            total_sales=Coalesce(Sum("total"), Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))),
            total_paid=Coalesce(Sum("tendered_amount"), Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))),
            total_due=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("total") - F("tendered_amount"),
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    )
                ),
                Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2)),
            ),
        ).order_by("-total_sales")
        return successResponse("Cashier report retrieved successfully.", data=paginatedResponse(rows, data))

    @staticmethod
    def customerStatement(customer_id, data, request):
        customer = commonQuery.findOneRecord(Customer, customer_id, request=request, tenant_config=True)
        if customer is None:
            return successResponse("Customer statement retrieved successfully.", data={"customer": None, "items": [], "total": 0})
        result = commonQuery.fetchPaginatedData(
            CustomerAccountHistory,
            {
                **(data or {}),
                "filter": {
                    **((data or {}).get("filter") or {}),
                    "customer_id": customer_id,
                },
            },
            [["operation", True, True], ["description", True, True]],
            {
                "attributes": [
                    "id",
                    "customer_id",
                    "customer__first_name",
                    "customer__last_name",
                    "amount",
                    "operation",
                    "previous_amount",
                    "next_amount",
                    "description",
                    "created_at",
                    "status",
                ],
                "sumField": ["amount"],
            },
            request=request,
            tenant_config=True,
        )
        result["customer"] = customer
        return successResponse("Customer statement retrieved successfully.", data=result)
