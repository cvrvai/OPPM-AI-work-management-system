"""Auth domain exceptions."""

from shared.exceptions.base import NotFoundError, ConflictError, UnauthorizedError


class AuthNotFoundError(NotFoundError):
    default_message = "User not found"


class AuthConflictError(ConflictError):
    default_message = "Email already registered"


class AuthUnauthorizedError(UnauthorizedError):
    default_message = "Invalid credentials"
