from typing import Optional

from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData
from apps.promotions.schemas import CouponIn, CouponUpdateIn, CustomerCouponUpdateIn
from apps.promotions.services import CouponService


router = Router(tags=["promotions"], auth=auth_bearer)


@router.post("/coupons/", response=ApiResponse)
@permissionRequired("promotions_create")
def createCoupon(request, payload: CouponIn):
    return CouponService.create(payloadData(payload), request)


@router.post("/coupons/get-transactions", response=ApiResponse)
@permissionRequired("promotions_view")
def getAllCoupons(request, payload: Optional[dict] = None):
    return CouponService.getAll(payload, request)


@router.get("/coupons/dropdown-list", response=ApiResponse)
@permissionRequired("promotions_view")
def getCouponDropdown(request):
    return CouponService.dropdownList(request)


@router.delete("/coupons/delete", response=ApiResponse)
@permissionRequired("promotions_delete")
def deleteCoupons(request, payload: BulkIdsSchema):
    return CouponService.delete(payloadData(payload), request)


@router.patch("/coupons/status", response=ApiResponse)
@permissionRequired("promotions_update")
def updateCouponStatus(request, payload: StatusUpdateSchema):
    return CouponService.updateStatus(payloadData(payload), request)


@router.get("/coupons/{coupon_id}", response=ApiResponse)
@permissionRequired("promotions_view")
def getCouponById(request, coupon_id: int):
    return CouponService.getById(coupon_id, request)


@router.put("/coupons/{coupon_id}", response=ApiResponse)
@permissionRequired("promotions_update")
def updateCoupon(request, coupon_id: int, payload: CouponUpdateIn):
    return CouponService.update(payloadData(payload, exclude_none=True), request, coupon_id)


@router.post("/customers/{customer_id}/coupons/get-transactions", response=ApiResponse)
@permissionRequired("promotions_view")
def getCustomerCoupons(request, customer_id: int, payload: Optional[dict] = None):
    return CouponService.getCustomerCoupons(customer_id, payload, request)


@router.post("/customers/{customer_id}/coupons/{customer_coupon_id}/history/get-transactions", response=ApiResponse)
@permissionRequired("promotions_view")
def getCustomerCouponHistory(
    request,
    customer_id: int,
    customer_coupon_id: int,
    payload: Optional[dict] = None,
):
    return CouponService.getCustomerCouponHistory(customer_id, customer_coupon_id, payload, request)


@router.post("/customers/coupons-generated/get-transactions", response=ApiResponse)
@permissionRequired("promotions_view")
def getGeneratedCustomerCoupons(request, payload: Optional[dict] = None):
    return CouponService.getGeneratedCoupons(payload, request)


@router.get("/customers/coupons-generated/{customer_coupon_id}", response=ApiResponse)
@permissionRequired("promotions_view")
def getGeneratedCustomerCouponById(request, customer_coupon_id: int):
    return CouponService.getGeneratedCouponById(customer_coupon_id, request)


@router.put("/customers/coupons-generated/{customer_coupon_id}", response=ApiResponse)
@permissionRequired("promotions_update")
def updateGeneratedCustomerCoupon(request, customer_coupon_id: int, payload: CustomerCouponUpdateIn):
    return CouponService.updateGeneratedCoupon(payloadData(payload, exclude_none=True), request, customer_coupon_id)
