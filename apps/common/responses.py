from typing import Any, Dict, Optional

from ninja import Schema


class ApiResponse(Schema):
    success: bool
    message: str
    data: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None


def successResponse(message: str, data: Any = None, meta: Optional[Dict[str, Any]] = None):
    return ApiResponse(success=True, message=message, data=data, meta=meta)


def errorResponse(message: str, data: Any = None, meta: Optional[Dict[str, Any]] = None):
    return ApiResponse(success=False, message=message, data=data, meta=meta)
