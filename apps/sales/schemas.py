from decimal import Decimal
from typing import List, Literal, Optional

from ninja import Field, Schema

OrderType = Literal["takeaway", "delivery"]
SaleStatus = Literal["pending", "ongoing", "ready", "delivered", "error", "not-available"]
ReturnType = Literal["refund", "exchange", "credit_note"]
ReturnCondition = Literal["unspoiled", "damaged"]


class SaleItemIn(Schema):
    product_id: int
    unit_id: Optional[int] = None
    unit_quantity_id: Optional[int] = None
    quantity: Decimal = Field(Decimal("1"), gt=0)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    discount_amount: Decimal = Field(Decimal("0"), ge=0)
    tax_amount: Decimal = Field(Decimal("0"), ge=0)


class OrderPaymentIn(Schema):
    payment_type: str
    amount: Decimal = Field(..., ge=0)
    reference_number: str = ""
    note: str = ""


class SaleCreateIn(Schema):
    draft_id: Optional[int] = None
    customer_id: Optional[int] = None
    register_id: Optional[int] = None
    order_type: OrderType = "takeaway"
    tax_group_id: Optional[int] = None
    tax_type: Optional[Literal["inclusive", "exclusive"]] = None
    discount_amount: Decimal = Field(Decimal("0"), ge=0)
    discount_percentage: Decimal = Field(Decimal("0"), ge=0)
    total_coupons: Decimal = Field(Decimal("0"), ge=0)
    shipping: Decimal = Field(Decimal("0"), ge=0)
    tax_amount: Decimal = Field(Decimal("0"), ge=0)
    tendered_amount: Decimal = Field(Decimal("0"), ge=0)
    note: str = ""
    coupon_codes: List[str] = Field(default_factory=list)
    items: List[SaleItemIn]
    payments: List[OrderPaymentIn] = Field(default_factory=list)


class SaleListIn(Schema):
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=100)
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
    note: str = ""
    payments: List[OrderPaymentIn]


class SaleStatusUpdateIn(Schema):
    status: SaleStatus
    note: str = ""


class OrderInstalmentCreateIn(Schema):
    due_date: str
    amount: Decimal = Field(..., gt=0)


class OrderInstalmentsCreateIn(Schema):
    total_installments: int = Field(0, ge=0)
    total_amount: Decimal = Field(Decimal("0"), ge=0)
    minimum_first_payment: Decimal = Field(Decimal("0"), ge=0)
    final_payment_date: Optional[str] = None
    lines: List[OrderInstalmentCreateIn] = Field(default_factory=list)


class OrderInstalmentUpdateIn(Schema):
    due_date: Optional[str] = None
    amount: Optional[Decimal] = Field(None, gt=0)


class InstallmentPayIn(Schema):
    amount: Decimal = Field(..., gt=0)
    payment_type: str = "cash-payment"
    reference_number: str = ""
    note: str = ""


class SaleReturnItemIn(Schema):
    sale_item_id: int
    quantity: Decimal = Field(..., gt=0)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    condition: ReturnCondition = "unspoiled"
    note: str = ""


class SaleReturnCreateIn(Schema):
    return_type: ReturnType = "refund"
    payment_type: Optional[str] = None
    exchange_sale_id: Optional[int] = None
    reference_number: str = ""
    note: str = ""
    items: List[SaleReturnItemIn]
