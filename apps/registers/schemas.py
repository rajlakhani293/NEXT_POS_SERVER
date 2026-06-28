from decimal import Decimal
from typing import Any, Literal, Optional

from ninja import Schema
from apps.common.schemas import ActiveStatus


class CashRegisterIn(Schema):
    name: str
    description: Optional[str] = None
    status: Optional[Any] = None
    register_status: Optional[Literal["closed", "disabled"]] = None


class CashRegisterUpdateIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Any] = None
    register_status: Optional[Literal["closed", "disabled"]] = None


class RegisterMoneyActionIn(Schema):
    register_id: int
    amount: Decimal = Decimal("0")
    note: Optional[str] = None
    description: Optional[str] = None


class RegisterStatusIn(Schema):
    register_id: int
    action: Literal["open", "close"]
    amount: Decimal = Decimal("0")
    note: Optional[str] = None
    description: Optional[str] = None


class SourceRegisterActionIn(Schema):
    amount: Decimal = Decimal("0")
    note: Optional[str] = None
    description: Optional[str] = None


class ShiftOpenIn(Schema):
    register_id: int
    amount: Decimal = Decimal("0")
    note: Optional[str] = None


class ShiftCloseIn(Schema):
    shift_id: int
    declared_cash: Decimal = Decimal("0")
    note: Optional[str] = None


class ShiftMoneyActionIn(Schema):
    shift_id: int
    amount: Decimal = Decimal("0")
    note: Optional[str] = None
