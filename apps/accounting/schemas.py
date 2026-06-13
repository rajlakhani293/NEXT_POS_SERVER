from decimal import Decimal
from typing import List, Literal, Optional

from ninja import Schema
from apps.common.schemas import ActiveStatus


AccountType = Literal["asset", "liability", "income", "expense", "equity"]
RuleAction = Literal["increase", "decrease"]
TransactionType = Literal["income", "expense", "transfer", "adjustment"]


class TransactionAccountIn(Schema):
    name: str
    code: Optional[str] = None
    account_type: AccountType
    parent_id: Optional[int] = None
    description: str = ""
    opening_balance: Decimal = Decimal("0")


class TransactionAccountUpdateIn(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    account_type: Optional[AccountType] = None
    parent_id: Optional[int] = None
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
    event_key: str
    action: RuleAction
    account_id: int
    offset_action: RuleAction
    offset_account_id: int


class TransactionRuleUpdateIn(Schema):
    event_key: Optional[str] = None
    action: Optional[RuleAction] = None
    account_id: Optional[int] = None
    offset_action: Optional[RuleAction] = None
    offset_account_id: Optional[int] = None
    status: Optional[ActiveStatus] = None


class AccountingSettingIn(Schema):
    expense_account_ids: List[int]
    paid_expense_offset_account_id: int
    sales_revenue_account_id: int
    order_cash_account_id: int
    receivable_account_id: int
    cogs_account_id: int
    inventory_account_id: int
    procurement_cash_account_id: int
    procurement_payable_account_id: int
