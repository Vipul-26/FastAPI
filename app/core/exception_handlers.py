"""Global exception handlers — uniform JSON error responses (Step 10.2 / 10.3)."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.errors import (
    CONFLICT,
    DATABASE_ERROR,
    INTERNAL_ERROR,
    VALIDATION_ERROR,
    error_type_for_status,
)

logger = logging.getLogger(__name__)


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Wrap HTTPException with a consistent error_type field."""
    detail = exc.detail
    if isinstance(detail, list):
        error_type = VALIDATION_ERROR
    else:
        error_type = error_type_for_status(exc.status_code)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "error_type": error_type},
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return Pydantic validation errors in the standard error shape."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": exc.errors(),
            "error_type": VALIDATION_ERROR,
        },
    )


async def integrity_error_handler(
    request: Request,
    exc: IntegrityError,
) -> JSONResponse:
    """Handle unique-constraint violations (e.g. duplicate email)."""
    logger.warning("IntegrityError on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": "Resource conflict",
            "error_type": CONFLICT,
        },
    )


async def database_error_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    """Handle unexpected database errors with rollback already applied."""
    logger.exception("Database error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Database error",
            "error_type": DATABASE_ERROR,
        },
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all for unexpected exceptions."""
    logger.exception("Unhandled error on %s", request.url.path)
    detail = str(exc) if settings.debug else "Internal server error"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": detail,
            "error_type": INTERNAL_ERROR,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI app."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
