from decimal import Decimal
from typing import List, Optional

from ninja import Field, Schema
from apps.common.schemas import ActiveStatus

class RewardRuleIn(Schema):
    from_amount: Decimal = Field(Decimal("0"), ge=0)
    to_amount: Decimal = Field(Decimal("0"), ge=0)
    reward: Decimal = Field(Decimal("0"), ge=0)


class RewardSystemIn(Schema):
    name: str
    coupon_id: int
    target: Decimal = Field(Decimal("0"), ge=0)
    description: str = ""
    from_amount: Decimal = Field(Decimal("0"), ge=0)
    to_amount: Decimal = Field(Decimal("0"), ge=0)
    reward: Decimal = Field(Decimal("0"), ge=0)
    rules: List[RewardRuleIn] = Field(default_factory=list)


class RewardSystemUpdateIn(Schema):
    name: Optional[str] = None
    coupon_id: Optional[int] = None
    target: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    from_amount: Optional[Decimal] = Field(None, ge=0)
    to_amount: Optional[Decimal] = Field(None, ge=0)
    reward: Optional[Decimal] = Field(None, ge=0)
    rules: Optional[List[RewardRuleIn]] = None
    status: Optional[ActiveStatus] = None


class RewardBalanceAdjustIn(Schema):
    customer_id: int
    reward_system_id: int
    points: Decimal = Field(..., ge=0)
    note: str = ""


class RewardSaleEarnIn(Schema):
    customer_id: int
    cart_total: Decimal = Field(..., ge=0)
    sale_order_id: Optional[int] = None
    note: str = ""


class RewardRedeemIn(Schema):
    customer_id: int
    reward_system_id: int
    points: Decimal = Field(..., ge=0)
    note: str = ""
