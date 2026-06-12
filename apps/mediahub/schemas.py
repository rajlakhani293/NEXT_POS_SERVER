from typing import Optional

from ninja import Schema

class MediaUpdateIn(Schema):
    alt_text: str = ""
    entity_type: str = ""
    entity_id: Optional[int] = None
