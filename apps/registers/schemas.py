from decimal import Decimal
from typing import Optional

from ninja import Schema
from apps.common.schemas import ActiveStatus

class CashRegisterIn(Schema):
    name: str
    code: Optional[str] = None
    location: str = ""


class CashRegisterUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    location: Optional[str] = None
    status: Optional[ActiveStatus] = None


class OpenShiftIn(Schema):
    register_id: Optional[int] = None
    opening_cash: Decimal = Decimal("0")
    note: str = ""


class CloseShiftIn(Schema):
    shift_id: Optional[int] = None
    declared_cash: Decimal = Decimal("0")
    note: str = ""


class CashMovementIn(Schema):
    shift_id: Optional[int] = None
    amount: Decimal
    note: str = ""
