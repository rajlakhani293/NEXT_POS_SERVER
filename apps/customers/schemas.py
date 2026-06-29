from decimal import Decimal
from typing import Dict, List, Optional, Union

from ninja import Field, Schema
from apps.common.schemas import ActiveStatus

class CustomerGroupIn(Schema):
    name: str
    description: str = ""
    minimal_credit_payment: Decimal = Field(Decimal("0"), ge=0)
    reward_system_id: Optional[int] = None


class CustomerGroupUpdateIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    minimal_credit_payment: Optional[Decimal] = Field(None, ge=0)
    reward_system_id: Optional[int] = None
    status: Optional[ActiveStatus] = None


class CustomerIn(Schema):
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    email: str = ""
    group_id: Optional[int] = None
    gender: str = ""
    birth_date: Optional[str] = None
    pobox: str = ""
    purchases_amount: Decimal = Decimal("0")
    owed_amount: Decimal = Decimal("0")
    credit_limit_amount: Decimal = Decimal("0")
    account_amount: Decimal = Decimal("0")
    billing_address_1: str = ""
    billing_address_2: str = ""
    billing_phone: str = ""
    billing_email: str = ""
    billing_first_name: str = ""
    billing_last_name: str = ""
    billing_country: str = ""
    billing_company_name: str = ""
    billing_pobox: str = ""
    billing_city: str = ""
    shipping_address_1: str = ""
    shipping_address_2: str = ""
    shipping_phone: str = ""
    shipping_email: str = ""
    shipping_first_name: str = ""
    shipping_last_name: str = ""
    shipping_country: str = ""
    shipping_company_name: str = ""
    shipping_pobox: str = ""
    shipping_city: str = ""


class CustomerUpdateIn(Schema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    group_id: Optional[int] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    pobox: Optional[str] = None
    purchases_amount: Optional[Decimal] = None
    owed_amount: Optional[Decimal] = None
    credit_limit_amount: Optional[Decimal] = None
    account_amount: Optional[Decimal] = None
    billing_address_1: Optional[str] = None
    billing_address_2: Optional[str] = None
    billing_phone: Optional[str] = None
    billing_email: Optional[str] = None
    billing_first_name: Optional[str] = None
    billing_last_name: Optional[str] = None
    billing_country: Optional[str] = None
    billing_company_name: Optional[str] = None
    billing_pobox: Optional[str] = None
    billing_city: Optional[str] = None
    shipping_address_1: Optional[str] = None
    shipping_address_2: Optional[str] = None
    shipping_phone: Optional[str] = None
    shipping_email: Optional[str] = None
    shipping_first_name: Optional[str] = None
    shipping_last_name: Optional[str] = None
    shipping_country: Optional[str] = None
    shipping_company_name: Optional[str] = None
    shipping_pobox: Optional[str] = None
    shipping_city: Optional[str] = None
    status: Optional[ActiveStatus] = None


class CustomerCreditIn(Schema):
    amount: Decimal
    direction: str = "increase"
    reason: str = "adjustment"
    note: str = ""


class CustomerSearchIn(Schema):
    search: Union[str, int] = ""


class CustomerAccountTransactionIn(Schema):
    operation: Optional[str] = None
    amount: Optional[Decimal] = None
    description: str = ""
    general: Optional[Dict[str, Union[str, Decimal]]] = None


class CustomerGroupTransferIn(Schema):
    from_group_id: int = Field(..., alias="from")
    to_group_id: int = Field(..., alias="to")
    ids: Union[str, List[int]]
