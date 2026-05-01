"""AI service exceptions."""
from shared.exceptions.base import NotFoundError, ForbiddenError, ValidationError


class AIModelNotFoundError(NotFoundError):
    default_message = "AI model not found"


class AIRateLimitError(ValidationError):
    default_message = "AI rate limit exceeded"
