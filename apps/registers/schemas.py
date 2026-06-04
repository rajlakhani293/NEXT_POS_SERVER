from decimal import Decimal
from typing import List, Optional, Union

from ninja import Schema


class DeleteSchema(Schema):
    ids: Union[int, List[int]]


class StatusUpdateSchema(Schema):
    ids: Union[int, List[int]]
    status: int


class OpenShiftIn(Schema):
    register_id: Optional[int] = None
    opening_cash: Decimal = Decimal("0")
    note: str = ""


class CloseShiftIn(Schema):
    shift_id: Optional[int] = None
    declared_cash: Decimal = Decimal("0")
    note: str = ""
