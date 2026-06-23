from typing import Optional

from ninja import Router

from apps.accounts.auth import auth_bearer
from apps.common.authz import permissionRequired
from apps.common.responses import ApiResponse
from apps.common.schemas import BulkIdsSchema, StatusUpdateSchema, payloadData
from apps.rewards.schemas import (
    RewardBalanceAdjustIn,
    RewardRedeemIn,
    RewardSaleEarnIn,
    RewardSystemIn,
    RewardSystemUpdateIn,
)
from apps.rewards.services import CustomerRewardService, RewardSystemService


router = Router(tags=["rewards"], auth=auth_bearer)


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
