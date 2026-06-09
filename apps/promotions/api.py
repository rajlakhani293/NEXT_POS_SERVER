from typing import Optional

from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permission_required
from apps.common.responses import ApiResponse
from apps.promotions.schemas import CouponIn, CouponUpdateIn, DeleteSchema, StatusUpdateSchema
from apps.promotions.services import CouponService


router = Router(tags=["promotions"], auth=auth_bearer)


@router.post("/coupons/", response=ApiResponse)
@permission_required("promotions_create")
def createCoupon(request, payload: CouponIn):
    return CouponService.create(payload.dict(), request)


@router.post("/coupons/get-transactions", response=ApiResponse)
@permission_required("promotions_view")
def getAllCoupons(request, payload: Optional[dict] = None):
    return CouponService.getAll(payload, request)


@router.get("/coupons/dropdown-list", response=ApiResponse)
@permission_required("promotions_view")
def getCouponDropdown(request):
    return CouponService.dropdownList(request)


@router.delete("/coupons/delete", response=ApiResponse)
@permission_required("promotions_delete")
def deleteCoupons(request, payload: DeleteSchema):
    return CouponService.delete(payload.dict(), request)


@router.patch("/coupons/status", response=ApiResponse)
@permission_required("promotions_update")
def updateCouponStatus(request, payload: StatusUpdateSchema):
    return CouponService.updateStatus(payload.dict(), request)


@router.get("/coupons/{coupon_id}", response=ApiResponse)
@permission_required("promotions_view")
def getCouponById(request, coupon_id: int):
    return CouponService.getById(coupon_id, request)


@router.put("/coupons/{coupon_id}", response=ApiResponse)
@permission_required("promotions_update")
def updateCoupon(request, coupon_id: int, payload: CouponUpdateIn):
    return CouponService.update(payload.dict(exclude_none=True), request, coupon_id)


@router.post("/customers/{customer_id}/coupons/get-transactions", response=ApiResponse)
@permission_required("promotions_view")
def getCustomerCoupons(request, customer_id: int, payload: Optional[dict] = None):
    return CouponService.getCustomerCoupons(customer_id, payload, request)


@router.post("/customers/{customer_id}/coupons/{customer_coupon_id}/history/get-transactions", response=ApiResponse)
@permission_required("promotions_view")
def getCustomerCouponHistory(
    request,
    customer_id: int,
    customer_coupon_id: int,
    payload: Optional[dict] = None,
):
    return CouponService.getCustomerCouponHistory(customer_id, customer_coupon_id, payload, request)
