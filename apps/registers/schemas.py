from decimal import Decimal
from typing import List, Literal, Optional, Union

from ninja import Schema


class DeleteSchema(Schema):
    ids: Union[int, List[int]]


class StatusUpdateSchema(Schema):
    ids: Union[int, List[int]]
    status: Literal[0, 1]


class CashRegisterIn(Schema):
    name: str
    code: Optional[str] = None
    location: str = ""


class CashRegisterUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    location: Optional[str] = None
    status: Optional[int] = None


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
