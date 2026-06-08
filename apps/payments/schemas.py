from typing import Optional

from ninja import Field, Schema


class PaymentTypeOut(Schema):
    value: str
    label: str


class PaymentTypeCreateIn(Schema):
    label: str = Field(..., min_length=1)
    identifier: Optional[str] = ""
    description: Optional[str] = ""
    is_enabled: bool = True
    sort_order: int = 0


class PaymentTypeUpdateIn(Schema):
    label: str = Field(..., min_length=1)
    identifier: Optional[str] = ""
    description: Optional[str] = ""
    is_enabled: bool = True
    sort_order: int = 0


class PaymentTypeListIn(Schema):
    page: int = 1
    limit: int = 10
    search: Optional[str] = ""
    filters: Optional[int] = 2
    sortBy: Optional[str] = "sort_order"
    sortDirection: Optional[str] = "ascending"


class PaymentTypeStatusIn(Schema):
    ids: list[int]
    status: int


class PaymentTypeBulkIdsIn(Schema):
    ids: list[int]
