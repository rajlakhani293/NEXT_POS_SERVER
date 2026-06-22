from typing import Optional

from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.reports.services import ReportService


router = Router(tags=["reports"], auth=auth_bearer)


@router.post("/dashboard-summary", response=ApiResponse)
@permission_required("reports_view")
def dashboardSummary(request, payload: Optional[dict] = None):
    return ReportService.dashboardSummary(payload or {}, request)


@router.post("/dashboard-snapshot/refresh", response=ApiResponse)
@permission_required("reports_view")
def refreshDashboardSnapshot(request, payload: Optional[dict] = None):
    return ReportService.refreshDashboardSnapshot(payload or {}, request)


@router.post("/dashboard/recompute", response=ApiResponse)
@permission_required("settings_update")
def recomputeDashboardReports(request, payload: Optional[dict] = None):
    return ReportService.enqueueDashboardRecompute(payload or {}, request)


@router.post("/customer-due", response=ApiResponse)
@permission_required("reports_view")
def customerDue(request, payload: Optional[dict] = None):
    return ReportService.customerDue(payload, request)


@router.post("/provider-payable", response=ApiResponse)
@permission_required("reports_view")
def providerPayable(request, payload: Optional[dict] = None):
    return ReportService.supplierPayable(payload, request)


@router.post("/supplier-payable", response=ApiResponse, deprecated=True, include_in_schema=False)
@permission_required("reports_view")
def supplierPayableAlias(request, payload: Optional[dict] = None):
    return ReportService.supplierPayable(payload, request)


@router.post("/Provider-payable", response=ApiResponse, deprecated=True, include_in_schema=False)
@permission_required("reports_view")
def providerPayableLegacy(request, payload: Optional[dict] = None):
    return ReportService.supplierPayable(payload, request)


@router.post("/stock-ledger", response=ApiResponse)
@permission_required("reports_view")
def stockLedger(request, payload: Optional[dict] = None):
    return ReportService.stockLedger(payload, request)


@router.post("/customer-credit-ledger", response=ApiResponse)
@permission_required("reports_view")
def customerCreditLedger(request, payload: Optional[dict] = None):
    return ReportService.customerCreditLedger(payload, request)


@router.post("/sale-report", response=ApiResponse)
@permission_required("reports_view")
def saleReport(request, payload: Optional[dict] = None):
    return ReportService.saleReport(payload, request)


@router.post("/sold-stock-report", response=ApiResponse)
@permission_required("reports_view")
def soldStockReport(request, payload: Optional[dict] = None):
    return ReportService.soldStockReport(payload, request)


@router.post("/profit-report", response=ApiResponse)
@permission_required("reports_view")
def profitReport(request, payload: Optional[dict] = None):
    return ReportService.profitReport(payload, request)


@router.post("/payment-types", response=ApiResponse)
@permission_required("reports_view")
def paymentTypesReport(request, payload: Optional[dict] = None):
    return ReportService.paymentTypesReport(payload, request)


@router.post("/transactions", response=ApiResponse)
@permission_required("reports_view")
def accountSummaryReport(request, payload: Optional[dict] = None):
    return ReportService.accountSummaryReport(payload, request)


@router.post("/products-report", response=ApiResponse)
@permission_required("reports_view")
def productsReport(request, payload: Optional[dict] = None):
    return ReportService.productsReport(payload, request)


@router.post("/low-stock", response=ApiResponse)
@permission_required("reports_view")
def lowStockReport(request, payload: Optional[dict] = None):
    return ReportService.lowStockReport(payload, request)


@router.post("/low-stock/detect", response=ApiResponse)
@permission_required("reports_view")
def detectLowStockProducts(request, payload: Optional[dict] = None):
    return ReportService.enqueueLowStockDetection(payload or {}, request)


@router.post("/stock-report", response=ApiResponse)
@permission_required("reports_view")
def stockReport(request, payload: Optional[dict] = None):
    return ReportService.stockReport(payload, request)


@router.post("/stock-combined", response=ApiResponse)
@permission_required("reports_view")
def stockCombinedReport(request, payload: Optional[dict] = None):
    return ReportService.stockCombinedReport(payload, request)


@router.post("/stock-combined/refresh", response=ApiResponse)
@permission_required("reports_view")
def refreshStockCombinedReport(request, payload: Optional[dict] = None):
    return ReportService.enqueueStockCombinedRefresh(payload or {}, request)


@router.post("/cashier-report", response=ApiResponse)
@permission_required("reports_view")
def cashierReport(request, payload: Optional[dict] = None):
    return ReportService.cashierReport(payload, request)


@router.post("/customers-statement/{customer_id}", response=ApiResponse)
@permission_required("reports_view")
def customerStatement(request, customer_id: int, payload: Optional[dict] = None):
    return ReportService.customerStatement(customer_id, payload, request)
