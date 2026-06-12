from typing import Optional

from ninja import Field, Schema

class NotificationIn(Schema):
    user_id: Optional[int] = None
    title: str
    message: str = ""
    notification_type: str = "info"
    source_type: str = "system"
    source_id: Optional[int] = None
    action_url: str = ""
    payload: dict = Field(default_factory=dict)
