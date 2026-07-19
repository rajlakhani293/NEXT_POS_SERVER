from decimal import Decimal
from typing import List, Literal, Optional

from ninja import Field, Schema

OrderType = Literal["takeaway", "delivery"]
SaleStatus = Literal["pending", "ongoing", "ready", "delivered", "error", "not-available"]
ReturnType = Literal["refund", "exchange", "credit_note"]
ReturnCondition = Literal["unspoiled", "damaged"]


class SaleItemIn(Schema):
    product_id: Optional[int] = None
    barcode: Optional[str] = None
    name: Optional[str] = None
    unit_name: Optional[str] = None
    mode: str = "normal"
    product_type: str = "product"
    rate: Decimal = Field(Decimal("0"), ge=0)
    unit_id: Optional[int] = None
    unit_quantity_id: Optional[int] = None
    quantity: Decimal = Field(Decimal("1"), gt=0)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    discount_amount: Decimal = Field(Decimal("0"), ge=0)
    tax_amount: Decimal = Field(Decimal("0"), ge=0)


class OrderPaymentIn(Schema):
    id: Optional[int] = None
    payment_type: str
    amount: Decimal = Field(..., ge=0)
    reference_number: str = ""
    note: str = ""


class OrderPaymentActionIn(Schema):
    identifier: Optional[str] = None
    payment_type: Optional[str] = None
    value: Optional[Decimal] = Field(None, ge=0)
    amount: Optional[Decimal] = Field(None, ge=0)
    register_id: Optional[int] = None
    reference_number: str = ""
    note: str = ""


class OrderInstalmentCreateIn(Schema):
    due_date: Optional[str] = None
    date: Optional[str] = None
    amount: Decimal = Field(..., gt=0)
    paid: bool = False


class SaleCreateIn(Schema):
    draft_id: Optional[int] = None
    title: str = ""
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
    support_instalments: bool = True
    total_instalments: int = Field(0, ge=0)
    final_payment_date: Optional[str] = None
    instalments: List[OrderInstalmentCreateIn] = Field(default_factory=list)


class OrderProductsActionIn(Schema):
    products: List[SaleItemIn]


class SaleUpdateIn(SaleCreateIn):
    draft_id: Optional[int] = None


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
    title: str = ""
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


class OrderInstalmentsCreateIn(Schema):
    total_installments: int = Field(0, ge=0)
    total_amount: Decimal = Field(Decimal("0"), ge=0)
    minimum_first_payment: Decimal = Field(Decimal("0"), ge=0)
    final_payment_date: Optional[str] = None
    instalment: Optional[OrderInstalmentCreateIn] = None
    lines: List[OrderInstalmentCreateIn] = Field(default_factory=list)


class OrderInstalmentUpdateIn(Schema):
    due_date: Optional[str] = None
    date: Optional[str] = None
    amount: Optional[Decimal] = Field(None, gt=0)


class OrderInstalmentPayloadIn(Schema):
    instalment: Optional[OrderInstalmentUpdateIn] = None
    due_date: Optional[str] = None
    date: Optional[str] = None
    amount: Optional[Decimal] = Field(None, gt=0)


class InstallmentPayIn(Schema):
    amount: Optional[Decimal] = Field(None, gt=0)
    payment_type: str = "cash-payment"
    reference_number: str = ""
    note: str = ""


class SaleReturnItemIn(Schema):
    sale_item_id: Optional[int] = None
    id: Optional[int] = None
    quantity: Decimal = Field(..., gt=0)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    condition: ReturnCondition = "unspoiled"
    note: str = ""
    description: str = ""


class SaleReturnCreateIn(Schema):
    return_type: ReturnType = "refund"
    payment_type: Optional[str] = None
    payment: Optional[dict] = None
    exchange_sale_id: Optional[int] = None
    reference_number: str = ""
    note: str = ""
    total: Optional[Decimal] = None
    refund_shipping: bool = False
    items: List[SaleReturnItemIn] = Field(default_factory=list)
    products: List[SaleReturnItemIn] = Field(default_factory=list)
