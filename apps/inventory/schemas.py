from decimal import Decimal
from typing import Optional

from ninja import Schema

class StockAdjustmentIn(Schema):
    product_id: int
    adjustment_type: str
    quantity: Decimal
    reason: str
    note: str = ""
    unit_cost: Decimal = Decimal("0")


class StockAdjustmentUpdateIn(Schema):
    reason: Optional[str] = None
    note: Optional[str] = None
