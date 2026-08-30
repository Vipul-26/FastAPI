"""Shared error codes for consistent API error responses (Step 10.1 / 10.3)."""

from http import HTTPStatus

# Machine-readable error_type values returned in JSON error bodies
VALIDATION_ERROR = "validation_error"
UNAUTHORIZED = "unauthorized"
FORBIDDEN = "forbidden"
NOT_FOUND = "not_found"
CONFLICT = "conflict"
BAD_REQUEST = "bad_request"
DATABASE_ERROR = "database_error"
INTERNAL_ERROR = "internal_error"


def error_type_for_status(status_code: int) -> str:
    """Map HTTP status codes to a stable error_type string."""
    mapping = {
        HTTPStatus.BAD_REQUEST: BAD_REQUEST,
        HTTPStatus.UNAUTHORIZED: UNAUTHORIZED,
        HTTPStatus.FORBIDDEN: FORBIDDEN,
        HTTPStatus.NOT_FOUND: NOT_FOUND,
        HTTPStatus.CONFLICT: CONFLICT,
        HTTPStatus.UNPROCESSABLE_ENTITY: VALIDATION_ERROR,
        HTTPStatus.INTERNAL_SERVER_ERROR: INTERNAL_ERROR,
    }
    return mapping.get(status_code, "http_error")
