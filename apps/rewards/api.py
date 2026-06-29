from typing import Optional

from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.commonQuery import commonQuery
from apps.common.responses import ApiResponse, successResponse
from apps.customers.models import CustomerCoupon
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData
from apps.rewards.schemas import (
    CustomerRewardUpdateIn,
    RewardBalanceAdjustIn,
    RewardRedeemIn,
    RewardSaleEarnIn,
    RewardSystemIn,
    RewardSystemUpdateIn,
)
from apps.rewards.services import CustomerRewardService, RewardSystemService


router = Router(tags=["rewards"], auth=auth_bearer)
sourceRouter = Router(tags=["reward-system"], auth=auth_bearer)


@router.post("/systems/", response=ApiResponse)
@permissionRequired("rewards_create")
def createRewardSystem(request, payload: RewardSystemIn):
    return RewardSystemService.create(payloadData(payload), request)


@router.post("/systems/get-transactions", response=ApiResponse)
@permissionRequired("rewards_view")
def getAllRewardSystems(request, payload: Optional[dict] = None):
    return RewardSystemService.getAll(payload, request)


@router.get("/systems/dropdown-list", response=ApiResponse)
@permissionRequired("rewards_view")
def getRewardSystemDropdown(request):
    return RewardSystemService.dropdownList(request)


@router.delete("/systems/delete", response=ApiResponse)
@permissionRequired("rewards_delete")
def deleteRewardSystems(request, payload: BulkIdsSchema):
    return RewardSystemService.delete(payloadData(payload), request)


@router.patch("/systems/status", response=ApiResponse)
@permissionRequired("rewards_update")
def updateRewardSystemStatus(request, payload: StatusUpdateSchema):
    return RewardSystemService.updateStatus(payloadData(payload), request)


@router.get("/systems/{reward_system_id}", response=ApiResponse)
@permissionRequired("rewards_view")
def getRewardSystemById(request, reward_system_id: int):
    return RewardSystemService.getById(reward_system_id, request)


@router.put("/systems/{reward_system_id}", response=ApiResponse)
@permissionRequired("rewards_update")
def updateRewardSystem(request, reward_system_id: int, payload: RewardSystemUpdateIn):
    return RewardSystemService.update(payloadData(payload, exclude_none=True), request, reward_system_id)


@router.get("/customers/{customer_id}/balance", response=ApiResponse)
@permissionRequired("rewards_view")
def getCustomerRewardBalance(request, customer_id: int):
    return CustomerRewardService.getBalance(customer_id, request)


@router.get("/customers/{customer_id}/rewards/{reward_id}", response=ApiResponse)
@permissionRequired("rewards_view")
def getCustomerRewardById(request, customer_id: int, reward_id: int):
    return CustomerRewardService.getById(customer_id, reward_id, request)


@router.put("/customers/{customer_id}/rewards/{reward_id}", response=ApiResponse)
@permissionRequired("rewards_update")
def updateCustomerReward(request, customer_id: int, reward_id: int, payload: CustomerRewardUpdateIn):
    return CustomerRewardService.update(customer_id, reward_id, payloadData(payload, exclude_none=True), request)


@router.post("/customers/balances/get-transactions", response=ApiResponse)
@permissionRequired("rewards_view")
def getCustomerRewardBalances(request, payload: Optional[dict] = None):
    return CustomerRewardService.getBalances(payload, request)


@router.post("/customers/redemptions/get-transactions", response=ApiResponse)
@permissionRequired("rewards_view")
def getCustomerRewardRedemptions(request, payload: Optional[dict] = None):
    return CustomerRewardService.getRedemptions(payload, request)


@router.post("/customers/earn", response=ApiResponse)
@permissionRequired("rewards_update")
def earnCustomerReward(request, payload: RewardBalanceAdjustIn):
    return CustomerRewardService.earn(payloadData(payload), request)


@router.post("/customers/earn-from-sale", response=ApiResponse)
@permissionRequired("rewards_update")
def earnCustomerRewardFromSale(request, payload: RewardSaleEarnIn):
    return CustomerRewardService.earnFromSale(payloadData(payload), request)


@router.post("/customers/redeem", response=ApiResponse)
@permissionRequired("rewards_update")
def redeemCustomerReward(request, payload: RewardRedeemIn):
    return CustomerRewardService.redeem(payloadData(payload), request)


@sourceRouter.get("/{reward_system_id}/rules", response=ApiResponse)
@permissionRequired("rewards_view")
def getSourceRewardRules(request, reward_system_id: int):
    data = RewardSystemService.getById(reward_system_id, request).data.get("rules", [])
    return successResponse("Reward system rules retrieved successfully.", data=data)


@sourceRouter.get("/{reward_system_id}/coupons", response=ApiResponse)
@permissionRequired("rewards_view")
def getSourceRewardCoupons(request, reward_system_id: int):
    customer_coupons = commonQuery.findAllRecords(
        CustomerCoupon,
        {"coupon__reward_systems__id": reward_system_id},
        {
            "attributes": [
                "id",
                "coupon_id",
                "coupon__name",
                "customer_id",
                "customer__first_name",
                "customer__last_name",
                "code",
                "limit_usage",
                "created_at",
                "status",
            ],
            "order": ["-created_at"],
        },
        request=request,
        tenant_config=True,
    )
    return successResponse("Reward coupons retrieved successfully.", data=customer_coupons)


@sourceRouter.post("/", response=ApiResponse)
@permissionRequired("rewards_create")
def createSourceRewardSystem(request, payload: RewardSystemIn):
    return RewardSystemService.create(payloadData(payload), request)


@sourceRouter.put("/{reward_system_id}", response=ApiResponse)
@permissionRequired("rewards_update")
def updateSourceRewardSystem(request, reward_system_id: int, payload: RewardSystemUpdateIn):
    return RewardSystemService.update(payloadData(payload, exclude_none=True), request, reward_system_id)


@sourceRouter.delete("/{reward_system_id}", response=ApiResponse)
@permissionRequired("rewards_delete")
def deleteSourceRewardSystem(request, reward_system_id: int):
    return RewardSystemService.delete({"ids": [reward_system_id]}, request)
