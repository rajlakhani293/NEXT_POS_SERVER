from decimal import Decimal
from typing import List, Literal, Optional, Union

from ninja import Schema


class DeleteSchema(Schema):
    ids: Union[int, List[int]]


class StatusUpdateSchema(Schema):
    ids: Union[int, List[int]]
    status: Literal[0, 1]


class CustomerGroupIn(Schema):
    name: str
    code: Optional[str] = None
    description: str = ""
    credit_limit: Decimal = Decimal("0")
    reward_system_id: Optional[int] = None


class CustomerGroupUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    reward_system_id: Optional[int] = None
    status: Optional[int] = None


class CustomerIn(Schema):
    name: str
    phone: str = ""
    email: str = ""
    customer_type: str = "retail"
    group_id: Optional[int] = None
    code: Optional[str] = None
    gender: str = ""
    birth_date: Optional[str] = None
    gst_number: str = ""
    company_name: str = ""
    opening_balance: Decimal = Decimal("0")
    credit_limit_amount: Decimal = Decimal("0")
    billing_address_line_1: str = ""
    billing_pincode: str = ""
    billing_city: str = ""
    billing_state_id: Optional[int] = None
    shipping_address_line_1: str = ""
    shipping_pincode: str = ""
    shipping_city: str = ""
    shipping_state_id: Optional[int] = None


class CustomerUpdateIn(Schema):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    customer_type: Optional[str] = None
    group_id: Optional[int] = None
    code: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    gst_number: Optional[str] = None
    company_name: Optional[str] = None
    opening_balance: Optional[Decimal] = None
    credit_limit_amount: Optional[Decimal] = None
    billing_address_line_1: Optional[str] = None
    billing_pincode: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state_id: Optional[int] = None
    shipping_address_line_1: Optional[str] = None
    shipping_pincode: Optional[str] = None
    shipping_city: Optional[str] = None
    shipping_state_id: Optional[int] = None
    status: Optional[int] = None


class CustomerCreditIn(Schema):
    amount: Decimal
    direction: str = "increase"
    reason: str = "adjustment"
    note: str = ""
