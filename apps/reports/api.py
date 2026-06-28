from typing import Optional

from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse
from apps.reports.services import ReportService


router = Router(tags=["reports"], auth=auth_bearer)
dashboardRouter = Router(tags=["dashboard"], auth=auth_bearer)


@router.post("/dashboard-summary", response=ApiResponse)
@permissionRequired("reports_view")
def dashboardSummary(request, payload: Optional[dict] = None):
    return ReportService.dashboardSummary(payload or {}, request)


@router.post("/dashboard-snapshot/refresh", response=ApiResponse)
@permissionRequired("reports_view")
def refreshDashboardSnapshot(request, payload: Optional[dict] = None):
    return ReportService.refreshDashboardSnapshot(payload or {}, request)


@router.post("/dashboard/recompute", response=ApiResponse)
@permissionRequired("settings_update")
def recomputeDashboardReports(request, payload: Optional[dict] = None):
    return ReportService.enqueueDashboardRecompute(payload or {}, request)


@dashboardRouter.get("/day", response=ApiResponse)
@permissionRequired("reports_view")
def dashboardDay(request):
    return ReportService.dashboardDay(request)


@dashboardRouter.get("/best-customers", response=ApiResponse)
@permissionRequired("reports_view")
def dashboardBestCustomers(request):
    return ReportService.dashboardBestCustomers(request)


@dashboardRouter.get("/best-cashiers", response=ApiResponse)
@permissionRequired("reports_view")
def dashboardBestCashiers(request):
    return ReportService.dashboardBestCashiers(request)


@dashboardRouter.get("/recent-orders", response=ApiResponse)
@permissionRequired("reports_view")
def dashboardRecentOrders(request):
    return ReportService.dashboardRecentOrders(request)


@dashboardRouter.get("/weeks", response=ApiResponse)
@permissionRequired("reports_view")
def dashboardWeeks(request):
    return ReportService.dashboardWeekReports(request)


@router.post("/customer-due", response=ApiResponse)
@permissionRequired("reports_view")
def customerDue(request, payload: Optional[dict] = None):
    return ReportService.customerDue(payload, request)


@router.post("/provider-payable", response=ApiResponse)
@permissionRequired("reports_view")
def providerPayable(request, payload: Optional[dict] = None):
    return ReportService.supplierPayable(payload, request)


@router.post("/stock-ledger", response=ApiResponse)
@permissionRequired("reports_view")
def stockLedger(request, payload: Optional[dict] = None):
    return ReportService.stockLedger(payload, request)


@router.post("/customer-credit-ledger", response=ApiResponse)
@permissionRequired("reports_view")
def customerCreditLedger(request, payload: Optional[dict] = None):
    return ReportService.customerCreditLedger(payload, request)


@router.post("/sale-report", response=ApiResponse)
@permissionRequired("reports_view")
def saleReport(request, payload: Optional[dict] = None):
    return ReportService.saleReport(payload, request)


@router.post("/sold-stock-report", response=ApiResponse)
@permissionRequired("reports_view")
def soldStockReport(request, payload: Optional[dict] = None):
    return ReportService.soldStockReport(payload, request)


@router.post("/profit-report", response=ApiResponse)
@permissionRequired("reports_view")
def profitReport(request, payload: Optional[dict] = None):
    return ReportService.profitReport(payload, request)


@router.post("/payment-types", response=ApiResponse)
@permissionRequired("reports_view")
def paymentTypesReport(request, payload: Optional[dict] = None):
    return ReportService.paymentTypesReport(payload, request)


@router.post("/transactions", response=ApiResponse)
@permissionRequired("reports_view")
def accountSummaryReport(request, payload: Optional[dict] = None):
    return ReportService.accountSummaryReport(payload, request)


@router.post("/products-report", response=ApiResponse)
@permissionRequired("reports_view")
def productsReport(request, payload: Optional[dict] = None):
    return ReportService.productsReport(payload, request)


@router.post("/low-stock", response=ApiResponse)
@permissionRequired("reports_view")
def lowStockReport(request, payload: Optional[dict] = None):
    return ReportService.lowStockReport(payload, request)


@router.post("/low-stock/detect", response=ApiResponse)
@permissionRequired("reports_view")
def detectLowStockProducts(request, payload: Optional[dict] = None):
    return ReportService.enqueueLowStockDetection(payload or {}, request)


@router.post("/stock-report", response=ApiResponse)
@permissionRequired("reports_view")
def stockReport(request, payload: Optional[dict] = None):
    return ReportService.stockReport(payload, request)


@router.post("/stock-combined", response=ApiResponse)
@permissionRequired("reports_view")
def stockCombinedReport(request, payload: Optional[dict] = None):
    return ReportService.stockCombinedReport(payload, request)


@router.post("/product-history-combined", response=ApiResponse)
@permissionRequired("reports_view")
def productHistoryCombinedReport(request, payload: Optional[dict] = None):
    return ReportService.stockCombinedReport(payload, request)


@router.post("/stock-combined/refresh", response=ApiResponse)
@permissionRequired("reports_view")
def refreshStockCombinedReport(request, payload: Optional[dict] = None):
    return ReportService.enqueueStockCombinedRefresh(payload or {}, request)


@router.post("/compute-combined-report", response=ApiResponse)
@permissionRequired("reports_view")
def computeCombinedReport(request, payload: Optional[dict] = None):
    return ReportService.recomputeStockCombined(payload or {}, request)


@router.post("/compute/{report_type}", response=ApiResponse)
@permissionRequired("reports_view")
def computeReport(request, report_type: str, payload: Optional[dict] = None):
    return ReportService.computeSourceReport(report_type, payload or {}, request)


@router.post("/cashier-report", response=ApiResponse)
@permissionRequired("reports_view")
def cashierReport(request, payload: Optional[dict] = None):
    return ReportService.cashierReport(payload, request)


@router.get("/cashier-report", response=ApiResponse)
@permissionRequired("reports_view")
def cashierReportGet(request):
    return ReportService.cashierReport({}, request)


@router.post("/customers-statement/{customer_id}", response=ApiResponse)
@permissionRequired("reports_view")
def customerStatement(request, customer_id: int, payload: Optional[dict] = None):
    return ReportService.customerStatement(customer_id, payload, request)


@router.post("/annual-report", response=ApiResponse)
@permissionRequired("reports_view")
def annualReport(request, payload: Optional[dict] = None):
    return ReportService.annualReport(payload, request)
