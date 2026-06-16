from decimal import Decimal
from typing import Literal, Optional

from ninja import Schema
from apps.common.schemas import ActiveStatus


AccountCategory = Literal["assets", "liabilities", "revenues", "expenses"]
RuleAction = Literal["increase", "decrease"]
TransactionType = Literal["income", "expense", "transfer", "adjustment"]


class TransactionAccountIn(Schema):
    name: str
    account: Optional[str] = None
    category_identifier: Optional[AccountCategory] = None
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
