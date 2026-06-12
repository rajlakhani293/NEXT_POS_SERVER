from decimal import Decimal
from typing import List, Optional

from ninja import Field, Schema
from apps.common.schemas import ActiveStatus

class RewardRuleIn(Schema):
    from_amount: Decimal = Decimal("0")
    to_amount: Decimal = Decimal("0")
    reward: int = 0


class RewardSystemIn(Schema):
    name: str
    coupon_id: int
    target: int = 0
    description: str = ""
    from_amount: Decimal = Decimal("0")
    to_amount: Decimal = Decimal("0")
    reward: int = 0
    rules: List[RewardRuleIn] = Field(default_factory=list)


class RewardSystemUpdateIn(Schema):
    name: Optional[str] = None
    coupon_id: Optional[int] = None
    target: Optional[int] = None
    description: Optional[str] = None
    from_amount: Optional[Decimal] = None
    to_amount: Optional[Decimal] = None
    reward: Optional[int] = None
    rules: Optional[List[RewardRuleIn]] = None
    status: Optional[ActiveStatus] = None


class RewardBalanceAdjustIn(Schema):
    customer_id: int
    reward_system_id: int
    points: int
    note: str = ""


class RewardSaleEarnIn(Schema):
    customer_id: int
    cart_total: Decimal
    sale_order_id: Optional[int] = None
    note: str = ""


class RewardRedeemIn(Schema):
    customer_id: int
    reward_system_id: int
    points: int
    note: str = ""
