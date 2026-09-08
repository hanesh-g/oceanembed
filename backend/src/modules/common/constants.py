"""Common constants used across the application."""

from collections.abc import Callable
from fastapi import HTTPException

from .exceptions import (
    DomainError,
    ResourceExistsError,
    ResourceNotFoundError,
    ValidationError,
)

# Generic error message for client-facing responses (never leak internal details)
GENERIC_ERROR_MESSAGE = "Something went wrong. Please try again."
SUPPORT_ID_LENGTH = 8

# Safety limits for queries that could be unbounded
DEFAULT_BATCH_SIZE = 100

EXCEPTION_MAPPING: dict[type[DomainError], Callable[[str], HTTPException]] = {
    ResourceNotFoundError: lambda message: HTTPException(status_code=404, detail="The requested resource was not found."),
    ResourceExistsError: lambda message: HTTPException(status_code=409, detail="This resource already exists."),
    ValidationError: lambda message: HTTPException(status_code=422, detail=message),
}
