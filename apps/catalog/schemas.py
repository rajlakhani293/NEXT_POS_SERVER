from decimal import Decimal
from typing import List, Optional, Union

from ninja import Schema


class DeleteSchema(Schema):
    ids: Union[int, List[int]]


class StatusUpdateSchema(Schema):
    ids: Union[int, List[int]]
    status: int


class CategoryIn(Schema):
    name: str
    parent_id: Optional[int] = None
    description: str = ""


class CategoryUpdateIn(Schema):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[int] = None


class BrandIn(Schema):
    name: str
    description: str = ""


class BrandUpdateIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None


class UnitGroupIn(Schema):
    name: str
    description: str = ""


class UnitGroupUpdateIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None


class UnitIn(Schema):
    unit_group_id: int
    name: str
    short_name: str
    factor: Decimal = Decimal("1")
    is_base_unit: bool = False


class UnitUpdateIn(Schema):
    unit_group_id: Optional[int] = None
    name: Optional[str] = None
    short_name: Optional[str] = None
    factor: Optional[Decimal] = None
    is_base_unit: Optional[bool] = None
    status: Optional[int] = None


class TaxGroupIn(Schema):
    name: str
    description: str = ""


class TaxGroupUpdateIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None


class TaxIn(Schema):
    tax_group_id: int
    name: str
    rate: Decimal


class TaxUpdateIn(Schema):
    tax_group_id: Optional[int] = None
    name: Optional[str] = None
    rate: Optional[Decimal] = None
    status: Optional[int] = None


class ProductIn(Schema):
    name: str
    sku: Optional[str] = None
    barcode: Optional[str] = None
    weight: Decimal = Decimal("0")
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    tax_group_id: Optional[int] = None
    unit_id: int
    product_type: str = "stock"
    description: Optional[str] = None
    purchase_price: Decimal = Decimal("0")
    selling_price: Decimal = Decimal("0")
    mrp: Decimal = Decimal("0")
    wholesale_price: Decimal = Decimal("0")
    is_tax_inclusive: bool = False
    current_stock: Decimal = Decimal("0")
    opening_stock: Decimal = Decimal("0")
    min_stock: Decimal = Decimal("0")
    max_stock: Decimal = Decimal("0")
    track_stock: bool = True
    allow_decimal_qty: bool = False
    expiry_tracking_enabled: bool = False


class ProductUpdateIn(Schema):
    name: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    weight: Optional[Decimal] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    tax_group_id: Optional[int] = None
    unit_id: Optional[int] = None
    product_type: Optional[str] = None
    description: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    mrp: Optional[Decimal] = None
    wholesale_price: Optional[Decimal] = None
    is_tax_inclusive: Optional[bool] = None
    min_stock: Optional[Decimal] = None
    max_stock: Optional[Decimal] = None
    track_stock: Optional[bool] = None
    allow_decimal_qty: Optional[bool] = None
    expiry_tracking_enabled: Optional[bool] = None
    status: Optional[int] = None


class ProductUnitQuantityIn(Schema):
    unit_id: int
    convert_unit_id: Optional[int] = None
    barcode: Optional[str] = None
    quantity: Decimal = Decimal("1")
    sale_price: Decimal = Decimal("0")
    purchase_price: Decimal = Decimal("0")
    is_default: bool = False
    scale_plu: str = ""


class ProductUnitQuantityUpdateIn(Schema):
    unit_id: Optional[int] = None
    convert_unit_id: Optional[int] = None
    barcode: Optional[str] = None
    quantity: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    purchase_price: Optional[Decimal] = None
    is_default: Optional[bool] = None
    scale_plu: Optional[str] = None
    status: Optional[int] = None
