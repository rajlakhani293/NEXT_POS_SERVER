from decimal import Decimal
from typing import Literal, Optional

from ninja import Schema
from apps.common.schemas import ActiveStatus


class CashRegisterIn(Schema):
    name: str
    description: Optional[str] = None


class CashRegisterUpdateIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ActiveStatus] = None


class RegisterMoneyActionIn(Schema):
    register_id: int
    amount: Decimal = Decimal("0")
    note: Optional[str] = None


class RegisterStatusIn(Schema):
    register_id: int
    action: Literal["open", "close"]
    amount: Decimal = Decimal("0")
    note: Optional[str] = None
