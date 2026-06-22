from typing import List, Literal, Union

from ninja import Schema

ActiveStatus = Literal[0, 1]


class BulkIdsSchema(Schema):
    ids: Union[int, List[int]]


class StatusUpdateSchema(BulkIdsSchema):
    status: ActiveStatus


def payloadData(payload, **kwargs):
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        return payload.model_dump(**kwargs)
    return payload.dict(**kwargs)
