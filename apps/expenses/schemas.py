from typing import Optional
from ninja import Schema


class ExpenseCategoryIn(Schema):
    name: str
    description: Optional[str] = None


class ExpenseCategoryUpdateIn(Schema):
    name: str
    description: Optional[str] = None


class ExpenseIn(Schema):
    category_id: int
    amount: float
    expense_date: str
    payment_type: Optional[str] = "cash-payment"
    shift_id: Optional[int] = None
    reference_number: Optional[str] = ""
    note: Optional[str] = ""


class ExpenseUpdateIn(Schema):
    category_id: Optional[int] = None
    amount: Optional[float] = None
    expense_date: Optional[str] = None
    payment_type: Optional[str] = None
    shift_id: Optional[int] = None
    reference_number: Optional[str] = None
    note: Optional[str] = None
