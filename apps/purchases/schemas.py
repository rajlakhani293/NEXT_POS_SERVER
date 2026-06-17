from decimal import Decimal
from typing import List, Optional

from ninja import Field, Schema

from apps.common.schemas import ActiveStatus


class SupplierIn(Schema):
    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address_1: Optional[str] = None
    address_2: Optional[str] = None
    description: Optional[str] = None


class SupplierUpdateIn(Schema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address_1: Optional[str] = None
    address_2: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ActiveStatus] = None


class PurchaseItemIn(Schema):
    product_id: int
    unit_id: int
    name: Optional[str] = None
    gross_purchase_price: Decimal = Decimal("0")
    net_purchase_price: Decimal = Decimal("0")
    purchase_price: Decimal
    quantity: Decimal
    available_quantity: Optional[Decimal] = None
    tax_group_id: Optional[int] = None
    barcode: Optional[str] = None
    expiration_date: Optional[str] = None
    tax_type: str = "exclusive"
    tax_value: Decimal = Decimal("0")
    total_purchase_price: Optional[Decimal] = None
    convert_unit_id: Optional[int] = None


class PurchaseOrderIn(Schema):
    provider_id: int
    name: Optional[str] = None
    invoice_reference: Optional[str] = None
    automatic_approval: bool = False
    delivery_time: Optional[str] = None
    invoice_date: Optional[str] = None
    payment_status: str = "unpaid"
    delivery_status: str = "pending"
    description: Optional[str] = None
    products: List[PurchaseItemIn] = Field(default_factory=list)


class PurchaseOrderUpdateIn(Schema):
    provider_id: Optional[int] = None
    name: Optional[str] = None
    invoice_reference: Optional[str] = None
    automatic_approval: Optional[bool] = None
    delivery_time: Optional[str] = None
    invoice_date: Optional[str] = None
    payment_status: Optional[str] = None
    delivery_status: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ActiveStatus] = None


class PurchaseReceiveItemIn(Schema):
    purchase_item_id: int
    received_quantity: Decimal


class PurchaseReceiveIn(Schema):
    items: List[PurchaseReceiveItemIn]
    note: str = ""


class PurchaseItemUpdateIn(Schema):
    product_id: Optional[int] = None
    unit_id: Optional[int] = None
    name: Optional[str] = None
    gross_purchase_price: Optional[Decimal] = None
    net_purchase_price: Optional[Decimal] = None
    purchase_price: Optional[Decimal] = None
    quantity: Optional[Decimal] = None
    available_quantity: Optional[Decimal] = None
    tax_group_id: Optional[int] = None
    barcode: Optional[str] = None
    expiration_date: Optional[str] = None
    tax_type: Optional[str] = None
    tax_value: Optional[Decimal] = None
    total_purchase_price: Optional[Decimal] = None
    convert_unit_id: Optional[int] = None


class PurchaseProductBulkUpdateItemIn(PurchaseItemIn):
    purchase_item_id: Optional[int] = None


class PurchaseProductsBulkUpdateIn(Schema):
    products: List[PurchaseProductBulkUpdateItemIn] = Field(default_factory=list)


class PurchaseStatusIn(Schema):
    payment_status: str
    reference_number: str = ""
    note: str = ""
