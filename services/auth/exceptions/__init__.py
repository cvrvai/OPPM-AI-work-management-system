"""Auth exceptions package."""

from exceptions.auth_errors import AuthNotFoundError, AuthConflictError, AuthUnauthorizedError

__all__ = ["AuthNotFoundError", "AuthConflictError", "AuthUnauthorizedError"]
