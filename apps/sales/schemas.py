from decimal import Decimal
from typing import List, Optional

from ninja import Schema


class SaleItemIn(Schema):
    product_id: int
    unit_id: Optional[int] = None
    quantity: Decimal = Decimal("1")
    unit_price: Optional[Decimal] = None
    discount_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")


class SalePaymentIn(Schema):
    payment_type: str
    amount: Decimal
    reference_number: str = ""
    note: str = ""


class SaleCreateIn(Schema):
    customer_id: Optional[int] = None
    register_id: Optional[int] = None
    shift_id: Optional[int] = None
    order_type: str = "pos"
    discount_amount: Decimal = Decimal("0")
    discount_percentage: Decimal = Decimal("0")
    coupon_discount_amount: Decimal = Decimal("0")
    shipping_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    tendered_amount: Decimal = Decimal("0")
    note: str = ""
    items: List[SaleItemIn]
    payments: List[SalePaymentIn] = []
