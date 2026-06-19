from decimal import Decimal
from typing import Literal, List, Optional

from ninja import Field, Schema

CouponType = Literal["flat_discount", "percentage_discount"]


class CouponIn(Schema):
    name: str
    code: str
    type: CouponType
    discount_value: Decimal = Field(..., ge=0)
    minimum_cart_value: Decimal = Field(Decimal("0"), ge=0)
    maximum_cart_value: Decimal = Field(Decimal("0"), ge=0)
    valid_until: Optional[str] = None
    valid_hours_start: Optional[str] = None
    valid_hours_end: Optional[str] = None
    limit_usage: int = Field(0, ge=0)
    product_ids: List[int] = Field(default_factory=list)
    category_ids: List[int] = Field(default_factory=list)
    customer_ids: List[int] = Field(default_factory=list)
    customer_group_ids: List[int] = Field(default_factory=list)


class CouponUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    type: Optional[CouponType] = None
    discount_value: Optional[Decimal] = Field(None, ge=0)
    minimum_cart_value: Optional[Decimal] = Field(None, ge=0)
    maximum_cart_value: Optional[Decimal] = Field(None, ge=0)
    valid_until: Optional[str] = None
    valid_hours_start: Optional[str] = None
    valid_hours_end: Optional[str] = None
    limit_usage: Optional[int] = Field(None, ge=0)
    product_ids: Optional[List[int]] = None
    category_ids: Optional[List[int]] = None
    customer_ids: Optional[List[int]] = None
    customer_group_ids: Optional[List[int]] = None
