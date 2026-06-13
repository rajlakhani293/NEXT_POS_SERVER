from decimal import Decimal
from typing import Optional

from ninja import Schema
from apps.common.schemas import ActiveStatus

class ExpenseCategoryIn(Schema):
    name: str
    code: Optional[str] = None
    account_id: Optional[int] = None
    description: str = ""


class ExpenseCategoryUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    account_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[ActiveStatus] = None


class ExpenseEntryIn(Schema):
    category_id: int
    amount: Decimal
    expense_date: str
    payment_type: str = "cash-payment"
    shift_id: Optional[int] = None
    note: str = ""
    reference_number: str = ""


class ExpenseEntryUpdateIn(Schema):
    category_id: Optional[int] = None
    amount: Optional[Decimal] = None
    expense_date: Optional[str] = None
    payment_type: Optional[str] = None
    shift_id: Optional[int] = None
    note: Optional[str] = None
    reference_number: Optional[str] = None
    status: Optional[ActiveStatus] = None
