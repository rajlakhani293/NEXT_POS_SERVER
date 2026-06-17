from decimal import Decimal
from typing import List, Optional

from ninja import Field, Schema


class SaleItemIn(Schema):
    product_id: int
    unit_id: Optional[int] = None
    unit_quantity_id: Optional[int] = None
    quantity: Decimal = Decimal("1")
    unit_price: Optional[Decimal] = None
    discount_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")


class OrderPaymentIn(Schema):
    payment_type: str
    amount: Decimal
    reference_number: str = ""
    note: str = ""


class SaleCreateIn(Schema):
    draft_id: Optional[int] = None
    customer_id: Optional[int] = None
    register_id: Optional[int] = None
    shift_id: Optional[int] = None
    order_type: str = "takeaway"
    discount_amount: Decimal = Decimal("0")
    discount_percentage: Decimal = Decimal("0")
    coupon_discount_amount: Decimal = Decimal("0")
    shipping_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    tendered_amount: Decimal = Decimal("0")
    note: str = ""
    coupon_codes: List[str] = Field(default_factory=list)
    items: List[SaleItemIn]
    payments: List[OrderPaymentIn] = Field(default_factory=list)


class SaleListIn(Schema):
    page: int = 1
    limit: int = 10
    search: Optional[str] = None
    status: Optional[int] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    sortBy: Optional[str] = None
    sortDirection: Optional[str] = None
    filter: Optional[dict] = None


class SaleHoldIn(Schema):
    customer_id: Optional[int] = None
    coupon_codes: List[str] = Field(default_factory=list)
    note: str = ""
    items: List[SaleItemIn]
    payments: List[OrderPaymentIn] = Field(default_factory=list)


class SaleVoidIn(Schema):
    note: str = ""


class SaleCollectDueIn(Schema):
    shift_id: Optional[int] = None
    note: str = ""
    payments: List[OrderPaymentIn]


class SaleStatusUpdateIn(Schema):
    status: str
    note: str = ""


class InstallmentLineCreateIn(Schema):
    due_date: str
    amount: Decimal


class InstallmentPlanCreateIn(Schema):
    total_installments: int = 0
    total_amount: Decimal = Decimal("0")
    minimum_first_payment: Decimal = Decimal("0")
    final_payment_date: Optional[str] = None
    lines: List[InstallmentLineCreateIn] = Field(default_factory=list)


class InstallmentLineUpdateIn(Schema):
    due_date: Optional[str] = None
    amount: Optional[Decimal] = None


class InstallmentPayIn(Schema):
    amount: Decimal
    payment_type: str = "cash-payment"
    shift_id: Optional[int] = None
    reference_number: str = ""
    note: str = ""


class SaleReturnItemIn(Schema):
    sale_item_id: int
    quantity: Decimal
    unit_price: Optional[Decimal] = None
    condition: str = "good"
    note: str = ""


class SaleReturnCreateIn(Schema):
    return_type: str = "refund"
    payment_type: Optional[str] = None
    shift_id: Optional[int] = None
    exchange_sale_id: Optional[int] = None
    reference_number: str = ""
    note: str = ""
    items: List[SaleReturnItemIn]
