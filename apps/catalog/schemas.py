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
    code: Optional[str] = None
    parent_id: Optional[int] = None
    description: str = ""


class CategoryUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    parent_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[int] = None


class BrandIn(Schema):
    name: str
    code: Optional[str] = None
    description: str = ""


class BrandUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None


class UnitGroupIn(Schema):
    name: str
    code: Optional[str] = None
    description: str = ""


class UnitGroupUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
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
    code: Optional[str] = None
    description: str = ""


class TaxGroupUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None


class TaxIn(Schema):
    tax_group_id: int
    name: str
    rate: Decimal
    is_inclusive: bool = False


class TaxUpdateIn(Schema):
    tax_group_id: Optional[int] = None
    name: Optional[str] = None
    rate: Optional[Decimal] = None
    is_inclusive: Optional[bool] = None
    status: Optional[int] = None


class ProductIn(Schema):
    name: str
    sku: str
    slug: Optional[str] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    tax_group_id: Optional[int] = None
    unit_group_id: Optional[int] = None
    product_type: str = "stock"
    description: str = ""
    purchase_price: Decimal = Decimal("0")
    selling_price: Decimal = Decimal("0")
    mrp: Decimal = Decimal("0")
    min_stock: Decimal = Decimal("0")
    track_stock: bool = True
    allow_decimal_qty: bool = False


class ProductUpdateIn(Schema):
    name: Optional[str] = None
    sku: Optional[str] = None
    slug: Optional[str] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    tax_group_id: Optional[int] = None
    unit_group_id: Optional[int] = None
    product_type: Optional[str] = None
    description: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    mrp: Optional[Decimal] = None
    min_stock: Optional[Decimal] = None
    track_stock: Optional[bool] = None
    allow_decimal_qty: Optional[bool] = None
    status: Optional[int] = None
