"""Project domain exceptions."""

from shared.exceptions.base import NotFoundError, ForbiddenError, ConflictError


class ProjectNotFoundError(NotFoundError):
    default_message = "Project not found"


class ProjectForbiddenError(ForbiddenError):
    default_message = "Not a member of this project"


class TaskNotFoundError(NotFoundError):
    default_message = "Task not found"


class TaskForbiddenError(ForbiddenError):
    default_message = "Not authorized to modify this task"
