"""Notification domain exceptions."""

from shared.exceptions.base import NotFoundError, ForbiddenError


class NotificationNotFoundError(NotFoundError):
    default_message = "Notification not found"


class NotificationForbiddenError(ForbiddenError):
    default_message = "Not authorized to access this notification"
