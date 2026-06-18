# type: ignore
from django.db.models import Count, F


def _tenantFilters(request):
    return {
        "company_id": request.user.company_id,
        "branch_id": request.user.branch_id,
        "status__in": [0, 1],
    }


class DomainActionService:
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

        User.objects.filter(id=sale_order.get("user_id") or request.user.id).update(
            total_sales=F("total_sales") + sale_order.get("total", 0),
            total_sales_count=F("total_sales_count") + 1,
        )
        order = Order.objects.get(
            id=sale_order["id"],
            company_id=request.user.company_id,
            branch_id=request.user.branch_id,
        )
        ensureOrderSettings(order, request)
        ReportService.refreshDashboardSnapshot({}, request)
        return order
