from decimal import Decimal
from typing import List, Optional

from ninja import Field, Schema
from apps.common.schemas import ActiveStatus

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
    status: Optional[ActiveStatus] = None


class PurchaseItemIn(Schema):
    product_id: int
    unit_quantity_id: Optional[int] = None
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
    items: List[PurchaseItemIn] = Field(default_factory=list)


class PurchaseOrderUpdateIn(Schema):
    supplier_id: Optional[int] = None
    code: Optional[str] = None
    order_date: Optional[str] = None
    expected_date: Optional[str] = None
    workflow_status: Optional[str] = None
    discount_amount: Optional[Decimal] = None
    shipping_amount: Optional[Decimal] = None
    note: Optional[str] = None
    status: Optional[ActiveStatus] = None


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


class PurchaseItemUpdateIn(Schema):
    product_id: Optional[int] = None
    unit_quantity_id: Optional[int] = None
    ordered_quantity: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None


class PurchaseProductBulkUpdateItemIn(Schema):
    purchase_item_id: Optional[int] = None
    product_id: int
    unit_quantity_id: Optional[int] = None
    ordered_quantity: Decimal
    cost_price: Decimal
    tax_amount: Decimal = Decimal("0")


class PurchaseProductsBulkUpdateIn(Schema):
    items: List[PurchaseProductBulkUpdateItemIn]


class PurchasePaymentStatusIn(Schema):
    payment_status: str
    amount: Optional[Decimal] = None
    payment_type: str = "cash-payment"
    reference_number: str = ""
    note: str = ""
