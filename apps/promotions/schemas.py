from decimal import Decimal
from typing import List, Optional

from ninja import Field, Schema

class CouponIn(Schema):
    name: str
    code: str
    type: str
    discount_value: Decimal
    minimum_cart_value: Decimal = Decimal("0")
    maximum_cart_value: Decimal = Decimal("0")
    valid_until: Optional[str] = None
    valid_hours_start: Optional[str] = None
    valid_hours_end: Optional[str] = None
    limit_usage: int = 0
    product_ids: List[int] = Field(default_factory=list)
    category_ids: List[int] = Field(default_factory=list)
    customer_ids: List[int] = Field(default_factory=list)
    customer_group_ids: List[int] = Field(default_factory=list)


class CouponUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    type: Optional[str] = None
    discount_value: Optional[Decimal] = None
    minimum_cart_value: Optional[Decimal] = None
    maximum_cart_value: Optional[Decimal] = None
    valid_until: Optional[str] = None
    valid_hours_start: Optional[str] = None
    valid_hours_end: Optional[str] = None
    limit_usage: Optional[int] = None
    product_ids: Optional[List[int]] = None
    category_ids: Optional[List[int]] = None
    customer_ids: Optional[List[int]] = None
    customer_group_ids: Optional[List[int]] = None
