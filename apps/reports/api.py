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


@router.post("/customer-due", response=ApiResponse)
@permission_required("reports_view")
def customerDue(request, payload: Optional[dict] = None):
    return ReportService.customerDue(payload, request)


@router.post("/supplier-payable", response=ApiResponse)
@permission_required("reports_view")
def supplierPayable(request, payload: Optional[dict] = None):
    return ReportService.supplierPayable(payload, request)


@router.post("/stock-ledger", response=ApiResponse)
@permission_required("reports_view")
def stockLedger(request, payload: Optional[dict] = None):
    return ReportService.stockLedger(payload, request)


@router.post("/customer-credit-ledger", response=ApiResponse)
@permission_required("reports_view")
def customerCreditLedger(request, payload: Optional[dict] = None):
    return ReportService.customerCreditLedger(payload, request)
