"""Workspace domain exceptions."""

from shared.exceptions.base import NotFoundError, ForbiddenError, ConflictError


class WorkspaceNotFoundError(NotFoundError):
    default_message = "Workspace not found"


class WorkspaceForbiddenError(ForbiddenError):
    default_message = "Not a member of this workspace"


class WorkspaceConflictError(ConflictError):
    default_message = "Workspace slug already taken"


class InviteNotFoundError(NotFoundError):
    default_message = "Invitation not found or expired"


class AlreadyMemberError(ConflictError):
    default_message = "User is already a member of this workspace"
