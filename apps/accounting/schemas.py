from decimal import Decimal
from typing import Optional

from ninja import Schema
from apps.common.schemas import ActiveStatus

class TransactionAccountIn(Schema):
    name: str
    code: Optional[str] = None
    account_type: str
    description: str = ""
    opening_balance: Decimal = Decimal("0")


class TransactionAccountUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    account_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ActiveStatus] = None


class ManualTransactionIn(Schema):
    account_id: int
    name: str
    transaction_type: str
    action_type: str
    amount: Decimal
    transaction_date: Optional[str] = None
    description: str = ""
    reference_number: str = ""
