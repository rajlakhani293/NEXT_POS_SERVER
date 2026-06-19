# type: ignore
from decimal import Decimal

from django.db.models import Count, F


def _tenantFilters(request):
    return {
        "company_id": request.user.company_id,
        "branch_id": request.user.branch_id,
        "status__in": [0, 1],
    }


class DomainActionService:
    @staticmethod
    def _money(value):
        return Decimal(str(value or 0))

    @staticmethod
    def refreshCategoryProductCount(category_id, request):
        if not category_id:
            return None
        from apps.catalog.models import Category, Product

        total_items = (
            Product.objects.filter(
                category_id=category_id,
                **_tenantFilters(request),
            )
            .aggregate(total=Count("id"))
            .get("total")
            or 0
        )
        Category.objects.filter(
            id=category_id,
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
        ).update(total_items=total_items)
        return total_items

    @staticmethod
    def afterProductCreated(product, request):
        return DomainActionService.refreshCategoryProductCount(product.get("category_id"), request)

    @staticmethod
    def afterProductUpdated(previous_product, updated_product, request):
        previous_category_id = previous_product.get("category_id") if previous_product else None
        current_category_id = updated_product.get("category_id") if updated_product else None
        DomainActionService.refreshCategoryProductCount(previous_category_id, request)
        if current_category_id != previous_category_id:
            DomainActionService.refreshCategoryProductCount(current_category_id, request)

    @staticmethod
    def afterSaleCreated(sale_order, request):
        from apps.accounts.models import User
        from apps.common.tenantDefaults import ensureOrderSettings
        from apps.reports.services import ReportService
        from apps.sales.models import Order

        if sale_order.get("payment_status") == "paid":
            DomainActionService.afterSalePaid(sale_order, request)
        order = Order.objects.get(
            id=sale_order["id"],
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
        )
        ensureOrderSettings(order, request)
        ReportService.refreshDashboardSnapshot({}, request)
        return order

    @staticmethod
    def afterSalePaid(sale_order, request):
        from apps.accounts.models import User

        User.objects.filter(id=sale_order.get("user_id") or request.user.id).update(
            total_sales=F("total_sales") + sale_order.get("total", 0),
            total_sales_count=F("total_sales_count") + 1,
        )

    @staticmethod
    def afterSaleVoided(sale_order, request):
        from apps.accounts.models import User
        from apps.reports.services import ReportService

        if sale_order.get("payment_status") == "paid":
            cashier_id = sale_order.get("user_id") or request.user.id
            cashier = User.objects.filter(id=cashier_id).first()
            if cashier:
                cashier.total_sales = max(DomainActionService._money(cashier.total_sales) - DomainActionService._money(sale_order.get("total")), Decimal("0"))
                cashier.total_sales_count = max(int(cashier.total_sales_count or 0) - 1, 0)
                cashier.save(update_fields=["total_sales", "total_sales_count"])
        ReportService.refreshDashboardSnapshot({}, request)

    @staticmethod
    def afterSaleRefunded(sale_order, return_order, request):
        from apps.accounts.models import User
        from apps.customers.models import Customer
        from apps.reports.services import ReportService

        refund_total = DomainActionService._money(return_order.get("total"))
        cashier_id = sale_order.get("user_id") or request.user.id
        cashier = User.objects.filter(id=cashier_id).first()
        if cashier:
            cashier.total_sales = max(DomainActionService._money(cashier.total_sales) - refund_total, Decimal("0"))
            cashier.save(update_fields=["total_sales"])
        if sale_order.get("customer_id"):
            customer = Customer.objects.filter(id=sale_order["customer_id"]).first()
            if customer:
                customer.purchases_amount = max(DomainActionService._money(customer.purchases_amount) - refund_total, Decimal("0"))
                customer.save(update_fields=["purchases_amount"])
        ReportService.refreshDashboardSnapshot({}, request)
