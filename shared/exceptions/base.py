"""
Base domain exception classes for OPPM microservices.

Services raise these in the business / repository layer.
Routers catch them and map to HTTPException.

Usage in a router:
    from shared.exceptions import NotFoundError
    from fastapi import HTTPException

    @router.get("/{id}")
    async def get_item(id: str, ...):
        try:
            return await service.get(id)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
"""


class OPPMError(Exception):
    """Root exception for all OPPM domain errors."""

    default_message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.default_message)


class NotFoundError(OPPMError):
    """Raised when a requested resource does not exist."""

    default_message = "Resource not found"


class ForbiddenError(OPPMError):
    """Raised when the caller lacks permission for an operation."""

    default_message = "Access denied"


class ConflictError(OPPMError):
    """Raised when an operation conflicts with existing state (e.g. duplicate)."""

    default_message = "Resource already exists"


class UnauthorizedError(OPPMError):
    """Raised when the caller is not authenticated."""

    default_message = "Authentication required"


class ValidationError(OPPMError):
    """Raised when input fails domain-level validation."""

    default_message = "Validation failed"
