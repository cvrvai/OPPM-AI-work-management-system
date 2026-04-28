"""Shared domain exception base classes for all OPPM microservices."""

from shared.exceptions.base import (
    OPPMError,
    NotFoundError,
    ForbiddenError,
    ConflictError,
    UnauthorizedError,
    ValidationError,
)

__all__ = [
    "OPPMError",
    "NotFoundError",
    "ForbiddenError",
    "ConflictError",
    "UnauthorizedError",
    "ValidationError",
]
