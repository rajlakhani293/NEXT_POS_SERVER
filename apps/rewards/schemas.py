from decimal import Decimal
from typing import List, Optional, Union

from ninja import Schema


class DeleteSchema(Schema):
    ids: Union[int, List[int]]


class StatusUpdateSchema(Schema):
    ids: Union[int, List[int]]
    status: int


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
    rules: List[RewardRuleIn] = []


class RewardSystemUpdateIn(Schema):
    name: Optional[str] = None
    coupon_id: Optional[int] = None
    target: Optional[int] = None
    description: Optional[str] = None
    from_amount: Optional[Decimal] = None
    to_amount: Optional[Decimal] = None
    reward: Optional[int] = None
    rules: Optional[List[RewardRuleIn]] = None
    status: Optional[int] = None


class RewardBalanceAdjustIn(Schema):
    customer_id: int
    reward_system_id: int
    points: int
    note: str = ""


class RewardRedeemIn(Schema):
    customer_id: int
    reward_system_id: int
    points: int
    note: str = ""
