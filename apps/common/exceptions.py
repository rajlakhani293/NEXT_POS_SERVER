from ninja.errors import HttpError

from apps.common.error_codes import HTTP_STATUS_DEFAULT_CODES


def api_error(status_code: int, code: str = "", message: str = "", data=None):
    return HttpError(
        status_code,
        {
            "code": code or HTTP_STATUS_DEFAULT_CODES.get(status_code, "SERVER_ERROR"),
            "message": message or "Something went wrong.",
            "data": data,
        },
    )
