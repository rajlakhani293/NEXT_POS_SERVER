from decimal import Decimal
from typing import List, Optional, Union

from ninja import Schema


class DeleteSchema(Schema):
    ids: Union[int, List[int]]


class StatusUpdateSchema(Schema):
    ids: Union[int, List[int]]
    status: int


class ExpenseCategoryIn(Schema):
    name: str
    code: Optional[str] = None
    description: str = ""


class ExpenseCategoryUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = None


class ExpenseEntryIn(Schema):
    category_id: int
    amount: Decimal
    expense_date: str
    payment_type: str = "cash"
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
    status: Optional[int] = None
