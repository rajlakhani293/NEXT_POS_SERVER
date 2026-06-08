from typing import List, Optional, Union

from ninja import Schema


class DeleteSchema(Schema):
    ids: Union[int, List[int]]


class MediaUpdateIn(Schema):
    alt_text: str = ""
    entity_type: str = ""
    entity_id: Optional[int] = None
