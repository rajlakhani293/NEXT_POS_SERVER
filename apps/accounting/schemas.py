from decimal import Decimal
from typing import List, Literal, Optional

from ninja import Schema
from apps.common.schemas import ActiveStatus


AccountCategory = Literal["assets", "liabilities", "revenues", "expenses", "equity"]
RuleAction = Literal["increase", "decrease"]
TransactionType = Literal["income", "expense", "transfer", "adjustment"]


class TransactionAccountIn(Schema):
    name: str
    category_identifier: AccountCategory
    account: Optional[str] = None
    sub_category_id: Optional[int] = None
    description: str = ""


class TransactionAccountUpdateIn(Schema):
    name: Optional[str] = None
    account: Optional[str] = None
    category_identifier: Optional[AccountCategory] = None
    sub_category_id: Optional[int] = None
    description: Optional[str] = None
    status: Optional[ActiveStatus] = None


class ManualTransactionIn(Schema):
    account_id: int
    name: str
    transaction_type: TransactionType = "expense"
    action_type: RuleAction = "increase"
    amount: Decimal
    transaction_date: Optional[str] = None
    description: str = ""
    reference_number: str = ""
    recurring: bool = False
    recurring_rule: str = ""
    next_run_at: Optional[str] = None


class TransactionRuleIn(Schema):
    on: str
    action: RuleAction
    account_id: int
    do: RuleAction
    offset_account_id: int


class TransactionRuleUpdateIn(Schema):
    on: Optional[str] = None
    action: Optional[RuleAction] = None
    account_id: Optional[int] = None
    do: Optional[RuleAction] = None
    offset_account_id: Optional[int] = None
    status: Optional[ActiveStatus] = None


class AccountingSettingsIn(Schema):
    expense_account_ids: Optional[List[int]] = None
    paid_expense_offset_account_id: Optional[int] = None
    sales_revenue_account_id: Optional[int] = None
    order_cash_account_id: Optional[int] = None
    receivable_account_id: Optional[int] = None
    cogs_account_id: Optional[int] = None
    inventory_account_id: Optional[int] = None
    procurement_cash_account_id: Optional[int] = None
    procurement_payable_account_id: Optional[int] = None
