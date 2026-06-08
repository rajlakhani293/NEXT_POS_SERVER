from decimal import Decimal
from typing import List, Optional, Union

from ninja import Schema


class DeleteSchema(Schema):
    ids: Union[int, List[int]]


class StatusUpdateSchema(Schema):
    ids: Union[int, List[int]]
    status: int


class SupplierIn(Schema):
    name: str
    code: Optional[str] = None
    email: str = ""
    phone: str = ""
    contact_person: str = ""
    tax_number: str = ""
    address: str = ""


class SupplierUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_person: Optional[str] = None
    tax_number: Optional[str] = None
    address: Optional[str] = None
    status: Optional[int] = None


class PurchaseItemIn(Schema):
    product_id: int
    ordered_quantity: Decimal
    received_quantity: Decimal = Decimal("0")
    cost_price: Decimal
    tax_amount: Decimal = Decimal("0")


class PurchaseOrderIn(Schema):
    supplier_id: int
    code: Optional[str] = None
    order_date: str
    expected_date: Optional[str] = None
    workflow_status: str = "draft"
    discount_amount: Decimal = Decimal("0")
    shipping_amount: Decimal = Decimal("0")
    note: str = ""
    items: List[PurchaseItemIn] = []


class PurchaseOrderUpdateIn(Schema):
    supplier_id: Optional[int] = None
    code: Optional[str] = None
    order_date: Optional[str] = None
    expected_date: Optional[str] = None
    workflow_status: Optional[str] = None
    discount_amount: Optional[Decimal] = None
    shipping_amount: Optional[Decimal] = None
    note: Optional[str] = None
    status: Optional[int] = None


class PurchaseReceiveItemIn(Schema):
    purchase_item_id: int
    received_quantity: Decimal


class PurchaseReceiveIn(Schema):
    items: List[PurchaseReceiveItemIn]
    note: str = ""


class PurchasePaymentIn(Schema):
    amount: Decimal
    paid_at: Optional[str] = None
    payment_type: str = "cash-payment"
    reference_number: str = ""
    note: str = ""
