from typing import List, Literal, Optional

from ninja import Field, Schema

OrderType = Literal["takeaway", "delivery"]
CurrencyPosition = Literal["before", "after"]
CurrencyPreferred = Literal["iso", "symbol"]
PosPreferredPrice = Literal["gross_prices", "net_prices"]
PosVat = Literal["disabled", "flat_vat", "variable_vat", "products_vat"]
OrdersCodeType = Literal["date_sequential", "random_code", "number_sequential", "sequential"]
QuotationExpiration = Literal["never", "3", "5", "10", "15", "30"]


class OptionSettingIn(Schema):
    orders_allow_partial: bool = False
    enable_customer_rewards: bool = False
    enable_credit_account: bool = False
    enable_cash_registers: bool = True
    allow_decimal_quantities: bool = True
    quick_product_enabled: bool = True
    pos_quick_product_default_unit: Optional[int] = None
    pos_layout: str = "grocery_shop"
    pos_sound_enabled: bool = True
    pos_complete_sale_audio: str = ""
    pos_new_item_audio: str = ""
    pos_order_sms: bool = False
    pos_enable_reordering: bool = False
    show_quantity: bool = True
    currency_symbol: str = "₹"
    currency_iso: str = "INR"
    currency_position: CurrencyPosition = "before"
    currency_preferred: CurrencyPreferred = "symbol"
    currency_thousand_separator: str = ","
    currency_decimal_separator: str = "."
    currency_precision: int = 2
    hide_empty_categories: bool = True
    unit_price_editable: bool = True
    default_change_payment_type: str = "cash-payment"
    pos_registers_default_change_payment_type: Optional[int] = None
    order_types: List[OrderType] = Field(default_factory=lambda: ["takeaway", "delivery"])
    pos_preferred_price: PosPreferredPrice = "net_prices"
    pos_vat: PosVat = "disabled"
    store_language: str = "en"
    registration_enabled: bool = False
    registration_role: str = ""
    registration_validated: bool = False
    recovery_enabled: bool = True
    date_format: str = "Y-m-d"
    datetime_format: str = "Y-m-d H:i"
    datetime_timezone: str = "UTC"
    orders_code_type: OrdersCodeType = "date_sequential"
    orders_allow_unpaid: bool = False
    orders_strict_instalments: bool = False
    orders_quotation_expiration: QuotationExpiration = "never"
    customers_default: Optional[int] = None
    customers_default_group: Optional[int] = None
    pos_tax_group: str = ""
    pos_tax_type: str = ""
    printing_document: str = "receipt"
    printing_enabled_for: str = "only_paid_orders"
    printing_gateway: str = "default"
    invoice_receipt_template: str = "default"
    invoice_receipt_logo: str = ""
    invoice_merge_similar_products: bool = False
    invoice_display_tax_breakdown: bool = False
    invoice_receipt_footer: str = ""
    invoice_receipt_column_a: str = ""
    invoice_receipt_column_b: str = ""
    reports_email: bool = False
    accounting_expenses_accounts: List[int] = Field(default_factory=list)
    accounting_default_paid_expense_offset_account: Optional[int] = None
    accounting_orders_revenues_account: Optional[int] = None
    accounting_orders_cash_account: Optional[int] = None
    accounting_orders_unpaid_account: Optional[int] = None
    accounting_orders_cogs_account: Optional[int] = None


class PaymentTypeOut(Schema):
    value: str
    label: str


class PaymentTypeCreateIn(Schema):
    label: str = Field(..., min_length=1)
    identifier: Optional[str] = ""
    description: Optional[str] = ""
    priority: int = 0
    active: bool = True


class PaymentTypeUpdateIn(Schema):
    label: str = Field(..., min_length=1)
    identifier: Optional[str] = ""
    description: Optional[str] = ""
    priority: int = 0
    active: bool = True


class PaymentTypeListIn(Schema):
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=100)
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


class JobListIn(Schema):
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=100)
    search: Optional[str] = ""
    sortBy: Optional[str] = "id"
    sortDirection: Optional[str] = "descending"


class FailedJobListIn(Schema):
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=100)
    search: Optional[str] = ""
    sortBy: Optional[str] = "id"
    sortDirection: Optional[str] = "descending"
