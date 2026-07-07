# type: ignore
from typing import Optional
from ninja import Body, Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse
from apps.reports.services import ReportService


router = Router(tags=["reports"], auth=auth_bearer)
dashboardRouter = Router(tags=["dashboard"], auth=auth_bearer)


@router.post("/dashboard-summary", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def dashboardSummary(request, payload: Optional[dict] = Body(None)):
    return ReportService.dashboardSummary(payload or {}, request)


@router.post("/dashboard-snapshot/refresh", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def refreshDashboardSnapshot(request, payload: Optional[dict] = Body(None)):
    return ReportService.refreshDashboardSnapshot(payload or {}, request)


@router.post("/dashboard/recompute", response=ApiResponse)
@permissionRequired("settings_update")
def recomputeDashboardReports(request, payload: Optional[dict] = Body(None)):
    return ReportService.enqueueDashboardRecompute(payload or {}, request)


@dashboardRouter.get("/day", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def dashboardDay(request):
    return ReportService.dashboardDay(request)


@dashboardRouter.get("/best-customers", response=ApiResponse)
@permissionRequired("pos.reports.customers")
def dashboardBestCustomers(request):
    return ReportService.dashboardBestCustomers(request)


@dashboardRouter.get("/best-cashiers", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def dashboardBestCashiers(request):
    return ReportService.dashboardBestCashiers(request)


@dashboardRouter.get("/recent-orders", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def dashboardRecentOrders(request):
    return ReportService.dashboardRecentOrders(request)


@dashboardRouter.get("/weeks", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def dashboardWeeks(request):
    return ReportService.dashboardWeekReports(request)


@router.post("/sale-report", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def saleReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.saleReport(payload, request)


@router.post("/sold-stock-report", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def soldStockReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.soldStockReport(payload, request)


@router.post("/profit-report", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def profitReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.profitReport(payload, request)


@router.post("/payment-types", response=ApiResponse)
@permissionRequired("pos.reports.payment-types")
def paymentTypesReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.paymentTypesReport(payload, request)


@router.post("/transactions", response=ApiResponse)
@permissionRequired("pos.reports.transactions")
def accountSummaryReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.accountSummaryReport(payload, request)


@router.post("/products-report", response=ApiResponse)
@permissionRequired("pos.reports.products-report")
def productsReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.productsReport(payload, request)


@router.post("/low-stock", response=ApiResponse)
@permissionRequired("pos.reports.low-stock")
def lowStockReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.lowStockReport(payload, request)


@router.post("/low-stock/detect", response=ApiResponse)
@permissionRequired("pos.reports.low-stock")
def detectLowStockProducts(request, payload: Optional[dict] = Body(None)):
    return ReportService.enqueueLowStockDetection(payload or {}, request)


@router.post("/stock-report", response=ApiResponse)
@permissionRequired("pos.reports.inventory")
def stockReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.stockReport(payload, request)


@router.post("/stock-combined", response=ApiResponse)
@permissionRequired("pos.reports.stock-history")
def stockCombinedReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.stockCombinedReport(payload, request)


@router.post("/product-history-combined", response=ApiResponse)
@permissionRequired("pos.reports.stock-history")
def productHistoryCombinedReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.stockCombinedReport(payload, request)


@router.post("/stock-combined/refresh", response=ApiResponse)
@permissionRequired("pos.reports.stock-history")
def refreshStockCombinedReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.enqueueStockCombinedRefresh(payload or {}, request)


@router.post("/compute-combined-report", response=ApiResponse)
@permissionRequired("pos.reports.stock-history")
def computeCombinedReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.recomputeStockCombined(payload or {}, request)


@router.post("/compute/{report_type}", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def computeReport(request, report_type: str, payload: Optional[dict] = Body(None)):
    return ReportService.computeSourceReport(report_type, payload or {}, request)


@router.post("/cashier-report", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def cashierReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.cashierReport(payload, request)


@router.get("/cashier-report", response=ApiResponse)
@permissionRequired("pos.reports.sales")
def cashierReportGet(request):
    return ReportService.cashierReport({}, request)


@router.post("/customers-statement/{customer_id}", response=ApiResponse)
@permissionRequired("pos.reports.customers-statement")
def customerStatement(request, customer_id: int, payload: Optional[dict] = Body(None)):
    return ReportService.customerStatement(customer_id, payload, request)


@router.post("/annual-report", response=ApiResponse)
@permissionRequired("pos.reports.yearly")
def annualReport(request, payload: Optional[dict] = Body(None)):
    return ReportService.annualReport(payload, request)
