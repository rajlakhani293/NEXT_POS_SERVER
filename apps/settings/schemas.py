from typing import List, Optional

from ninja import Field, Schema


class OptionSettingIn(Schema):
    allow_partial_orders: bool = False
    enable_customer_rewards: bool = False
    enable_credit_account: bool = False
    enable_cash_registers: bool = True
    allow_decimal_quantities: bool = True
    quick_product_enabled: bool = True
    show_quantity: bool = True
    currency_precision: int = 2
    hide_empty_categories: bool = True
    unit_price_editable: bool = True
    default_change_payment_type: str = "cash-payment"
    order_types: List[str] = ["takeaway", "delivery"]


class PaymentTypeOut(Schema):
    value: str
    label: str


class PaymentTypeCreateIn(Schema):
    label: str = Field(..., min_length=1)
    identifier: Optional[str] = ""
    description: Optional[str] = ""
    priority: int = 0


class PaymentTypeUpdateIn(Schema):
    label: str = Field(..., min_length=1)
    identifier: Optional[str] = ""
    description: Optional[str] = ""
    priority: int = 0


class PaymentTypeListIn(Schema):
    page: int = 1
    limit: int = 10
    search: Optional[str] = ""
    filters: Optional[int] = 2
    sortBy: Optional[str] = "priority"
    sortDirection: Optional[str] = "ascending"


class MediaUpdateIn(Schema):
    name: Optional[str] = None
    extension: Optional[str] = None
    slug: Optional[str] = None


class NotificationIn(Schema):
    user_id: Optional[int] = None
    identifier: str = ""
    title: str
    description: str = ""
    message: str = ""
    url: str = "#"
    source: str = "system"
    source_type: str = "system"
    dismissable: bool = True
    actions: Optional[dict] = None
