from typing import Optional

from ninja import Schema

class MediaUpdateIn(Schema):
    name: Optional[str] = None
    extension: Optional[str] = None
    slug: Optional[str] = None
