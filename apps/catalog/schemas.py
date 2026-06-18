from datetime import datetime
from typing import List, Optional

from ninja import Schema

from apps.common.schemas import ActiveStatus


class CategoryIn(Schema):
    name: str
    parent_id: Optional[int] = None
    media_id: int = 0
    preview_url: Optional[str] = None
    displays_on_pos: bool = True
    scale_range_id: Optional[int] = None
    total_items: int = 0
    position: int = 0
    description: str = ""


class CategoryUpdateIn(Schema):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    media_id: Optional[int] = None
    preview_url: Optional[str] = None
    displays_on_pos: Optional[bool] = None
    scale_range_id: Optional[int] = None
    total_items: Optional[int] = None
    position: Optional[int] = None
    description: Optional[str] = None
    status: Optional[ActiveStatus] = None


class UnitGroupIn(Schema):
    name: str
    description: str = ""


class UnitGroupUpdateIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ActiveStatus] = None


class UnitIn(Schema):
    group_id: int
    name: str
    identifier: str
    description: str = ""
    value: float = 1
    preview_url: Optional[str] = None
    base_unit: bool = False


class UnitUpdateIn(Schema):
    group_id: Optional[int] = None
    name: Optional[str] = None
    identifier: Optional[str] = None
    description: Optional[str] = None
    value: Optional[float] = None
    preview_url: Optional[str] = None
    base_unit: Optional[bool] = None
    status: Optional[ActiveStatus] = None


class TaxGroupIn(Schema):
    name: str
    description: str = ""


class TaxGroupUpdateIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ActiveStatus] = None


class TaxIn(Schema):
    tax_group_id: int
    name: str
    description: str = ""
    rate: float


class TaxUpdateIn(Schema):
    tax_group_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    rate: Optional[float] = None
    status: Optional[ActiveStatus] = None


class ProductIn(Schema):
    name: str
    tax_type: Optional[str] = None
    tax_group_id: Optional[int] = None
    tax_value: float = 0
    product_type: str = "product"
    type: str = "materialized"
    accurate_tracking: bool = False
    auto_cogs: bool = True
    stock_management: str = "enabled"
    barcode: Optional[str] = None
    barcode_type: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    thumbnail_id: Optional[int] = None
    category_id: Optional[int] = None
    parent_id: Optional[int] = None
    unit_group_id: Optional[int] = None
    on_expiration: str = "prevent_sales"
    expires: bool = False
    searchable: bool = True
    position: int = 0
    pinned: bool = False


class ProductUpdateIn(Schema):
    name: Optional[str] = None
    tax_type: Optional[str] = None
    tax_group_id: Optional[int] = None
    tax_value: Optional[float] = None
    product_type: Optional[str] = None
    type: Optional[str] = None
    accurate_tracking: Optional[bool] = None
    auto_cogs: Optional[bool] = None
    stock_management: Optional[str] = None
    barcode: Optional[str] = None
    barcode_type: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    thumbnail_id: Optional[int] = None
    category_id: Optional[int] = None
    parent_id: Optional[int] = None
    unit_group_id: Optional[int] = None
    on_expiration: Optional[str] = None
    expires: Optional[bool] = None
    searchable: Optional[bool] = None
    position: Optional[int] = None
    pinned: Optional[bool] = None
    status: Optional[ActiveStatus] = None


class ProductUnitQuantityIn(Schema):
    type: str = "product"
    preview_url: Optional[str] = None
    expiration_date: Optional[datetime] = None
    unit_id: int
    barcode: Optional[str] = None
    scale_plu: Optional[str] = None
    is_weighable: bool = False
    quantity: float = 0
    low_quantity: float = 0
    stock_alert_enabled: bool = False
    sale_price: float = 0
    sale_price_edit: float = 0
    sale_price_net: float = 0
    sale_price_gross: float = 0
    sale_price_tax: float = 0
    wholesale_price: float = 0
    wholesale_price_edit: float = 0
    wholesale_price_gross: float = 0
    wholesale_price_net: float = 0
    wholesale_price_tax: float = 0
    custom_price: float = 0
    custom_price_edit: float = 0
    custom_price_gross: float = 0
    custom_price_net: float = 0
    custom_price_tax: float = 0
    visible: bool = True
    convert_unit_id: Optional[int] = None
    cogs: float = 0


class ProductUnitQuantityUpdateIn(Schema):
    type: Optional[str] = None
    preview_url: Optional[str] = None
    expiration_date: Optional[datetime] = None
    unit_id: Optional[int] = None
    barcode: Optional[str] = None
    scale_plu: Optional[str] = None
    is_weighable: Optional[bool] = None
    quantity: Optional[float] = None
    low_quantity: Optional[float] = None
    stock_alert_enabled: Optional[bool] = None
    sale_price: Optional[float] = None
    sale_price_edit: Optional[float] = None
    sale_price_net: Optional[float] = None
    sale_price_gross: Optional[float] = None
    sale_price_tax: Optional[float] = None
    wholesale_price: Optional[float] = None
    wholesale_price_edit: Optional[float] = None
    wholesale_price_gross: Optional[float] = None
    wholesale_price_net: Optional[float] = None
    wholesale_price_tax: Optional[float] = None
    custom_price: Optional[float] = None
    custom_price_edit: Optional[float] = None
    custom_price_gross: Optional[float] = None
    custom_price_net: Optional[float] = None
    custom_price_tax: Optional[float] = None
    visible: Optional[bool] = None
    convert_unit_id: Optional[int] = None
    cogs: Optional[float] = None
    status: Optional[ActiveStatus] = None


class ProductAdjustmentUnitIn(Schema):
    unit_id: int
    sale_price: float = 0


class ProductAdjustmentItemIn(Schema):
    id: int
    adjust_action: str
    adjust_quantity: float
    adjust_reason: str = ""
    adjust_unit: ProductAdjustmentUnitIn
    procurement_product_id: Optional[int] = None


class ProductAdjustmentIn(Schema):
    products: List[ProductAdjustmentItemIn]
