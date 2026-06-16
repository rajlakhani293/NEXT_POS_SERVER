# type: ignore
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models.functions import TruncDate

from apps.common.commonQuery import commonQuery
from apps.common.helpers import jsonsafe
from apps.common.responses import successResponse
from apps.catalog.models import Product, ProductHistory, ProductUnitQuantity
from apps.customers.models import Customer, CustomerAccountHistory
from apps.expenses.models import ExpenseEntry
from apps.payments.models import SalePayment
from apps.purchases.models import PurchaseOrder, Supplier
from apps.registers.models import CashierShift
from apps.reports.models import DashboardDay, DashboardMonth
from apps.sales.models import SaleItem, SaleOrder


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
            total_purchase=Coalesce(Sum("value"), zero),
            total_purchase_due=Coalesce(Sum("value", filter=Q(payment_status="unpaid")), zero),
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
            total_supplier_payable=Coalesce(Sum("amount_due"), zero),
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
            [["first_name", True, True], ["last_name", True, True], ["phone", True, True]],
            {"attributes": ["id", "first_name", "last_name", "phone", "owed_amount", "credit_limit_amount", "account_amount", "status"]},
            request=request,
            tenant_config=True,
        )
        return successResponse("Customer due report retrieved successfully.", data=result)

    @staticmethod
    def supplierPayable(data, request):
        result = commonQuery.fetchPaginatedData(
            Supplier,
            data,
            [["first_name", True, True], ["last_name", True, True], ["phone", True, True], ["email", True, True]],
            {"attributes": ["id", "first_name", "last_name", "phone", "email", "amount_due", "amount_paid", "status"]},
            request=request,
            tenant_config=True,
        )
        for item in result["items"]:
            item["name"] = " ".join([part for part in [item.get("first_name"), item.get("last_name")] if part]).strip()
            item["payable_amount"] = item.get("amount_due")
        return successResponse("Supplier payable report retrieved successfully.", data=result)

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
            SaleOrder,
            data,
            [["code", True, True], ["customer__name", True, True], ["cashier__full_name", True, True], ["payment_status", True, True]],
            {
                "attributes": [
                    "id",
                    "code",
                    "customer__name",
                    "cashier__full_name",
                    "order_type",
                    "payment_status",
                    "subtotal",
                    "discount_amount",
                    "tax_amount",
                    "total",
                    "tendered_amount",
                    "due_amount",
                    "total_items",
                    "total_quantity",
                    "created_at",
                    "status",
                ],
                "sumField": ["total", "tendered_amount", "due_amount"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Sale report retrieved successfully.", data=result)

    @staticmethod
    def soldStockReport(data, request):
        field_config = [["product__name", True, True], ["sale_order__code", True, True]]
        result = commonQuery.fetchPaginatedData(
            SaleItem,
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
        queryset = SaleItem.objects.filter(**filters).annotate(
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
            SalePayment,
            data,
            [["payment_type", True, True], ["reference_number", True, True], ["sale_order__code", True, True]],
            {
                "attributes": [
                    "id",
                    "sale_order_id",
                    "sale_order__code",
                    "payment_type",
                    "shift_id",
                    "amount",
                    "paid_at",
                    "reference_number",
                    "note",
                    "status",
                ],
                "sumField": ["amount"],
            },
            request=request,
            tenant_config=True,
        )
        return successResponse("Payment types report retrieved successfully.", data=result)

    @staticmethod
    def productsReport(data, request):
        queryset = ProductUnitQuantity.objects.filter(
            **tenantFilter(request),
        ).annotate(
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
        queryset = ProductUnitQuantity.objects.filter(
            **tenantFilter(request),
            stock_alert_enabled=True,
            quantity__lte=F("low_quantity"),
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
    def stockReport(data, request):
        queryset = ProductUnitQuantity.objects.filter(**tenantFilter(request))
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
    def cashierReport(data, request):
        queryset = SaleOrder.objects.filter(**{**tenantFilter(request), **dateFilter("created_at", data)})
        if not request.user.is_superuser:
            queryset = queryset.filter(cashier_id=request.user.id)
        rows = queryset.values("cashier_id", "cashier__full_name").annotate(
            order_count=Count("id"),
            total_sales=Coalesce(Sum("total"), Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))),
            total_paid=Coalesce(Sum("tendered_amount"), Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))),
            total_due=Coalesce(Sum("due_amount"), Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))),
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
