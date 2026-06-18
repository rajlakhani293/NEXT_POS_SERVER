from typing import Optional

from ninja import Field, Schema

class NotificationIn(Schema):
    user_id: Optional[int] = None
    identifier: str = ""
    title: str
    description: str = ""
    message: str = ""
    url: str = "#"
    source: str = "system"
    source_type: str = "system"
    dismissable: bool = True
    actions: Optional[dict] = None
