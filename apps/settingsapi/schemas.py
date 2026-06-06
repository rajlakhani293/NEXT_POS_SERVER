from typing import List

from ninja import Schema


class BusinessSettingIn(Schema):
    allow_partial_orders: bool = False
    enable_customer_rewards: bool = False
    enable_credit_account: bool = False
    enable_cash_registers: bool = True
    order_types: List[str] = ["take_order", "delivery"]
