from typing import List

from ninja import Schema


class BusinessSettingIn(Schema):
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
