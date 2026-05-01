"""Git service exceptions."""
from shared.exceptions.base import NotFoundError, ForbiddenError


class RepoNotFoundError(NotFoundError):
    default_message = "Repository not found"


class WebhookValidationError(ForbiddenError):
    default_message = "Webhook signature validation failed"
