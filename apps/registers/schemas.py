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
