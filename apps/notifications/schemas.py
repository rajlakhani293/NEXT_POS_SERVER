from typing import List, Optional, Union

from ninja import Schema


class DeleteSchema(Schema):
    ids: Union[int, List[int]]


class NotificationIn(Schema):
    user_id: Optional[int] = None
    title: str
    message: str = ""
    notification_type: str = "info"
    source_type: str = "system"
    source_id: Optional[int] = None
    action_url: str = ""
    payload: dict = {}


class MarkReadIn(Schema):
    ids: Union[int, List[int]]
