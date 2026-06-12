from typing import List, Literal, Union

from ninja import Schema

ActiveStatus = Literal[0, 1]


class BulkIdsSchema(Schema):
    ids: Union[int, List[int]]


class StatusUpdateSchema(BulkIdsSchema):
    status: ActiveStatus
