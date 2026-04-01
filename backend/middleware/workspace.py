"""
Workspace membership verification middleware.
Ensures the current user belongs to the requested workspace.
"""

from dataclasses import dataclass
from fastapi import Depends, HTTPException, status, Path
from middleware.auth import CurrentUser, get_current_user
from database import get_db


@dataclass
class WorkspaceContext:
    """Workspace context injected into route handlers."""
    workspace_id: str
    user: CurrentUser
    role: str  # owner | admin | member | viewer
    member_id: str  # workspace_members.id

    @property
    def is_admin(self) -> bool:
        return self.role in ("owner", "admin")

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def can_write(self) -> bool:
        return self.role in ("owner", "admin", "member")


async def get_workspace_context(
    workspace_id: str = Path(..., description="Workspace UUID"),
    user: CurrentUser = Depends(get_current_user),
) -> WorkspaceContext:
    """
    Dependency that verifies user is a member of the workspace.
    Returns WorkspaceContext with role information.
    """
    db = get_db()
    result = (
        db.table("workspace_members")
        .select("id, role")
        .eq("workspace_id", workspace_id)
        .eq("user_id", user.id)
        .maybe_single()
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this workspace",
        )

    return WorkspaceContext(
        workspace_id=workspace_id,
        user=user,
        role=result.data["role"],
        member_id=result.data["id"],
    )


def require_admin(ws: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
    """Dependency that requires admin or owner role."""
    if not ws.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or owner role required",
        )
    return ws


def require_write(ws: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
    """Dependency that requires at least member role (not viewer)."""
    if not ws.can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access required (member, admin, or owner role)",
        )
    return ws
