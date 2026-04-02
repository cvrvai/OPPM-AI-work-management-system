"""MCP endpoint — exposes MCP tools via HTTP for AI model integration."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from shared.auth import get_current_user, get_workspace_context, WorkspaceContext
from infrastructure.mcp.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)
router = APIRouter()


class MCPToolCallRequest(BaseModel):
    tool: str
    params: dict = {}


class MCPToolCallResponse(BaseModel):
    tool: str
    result: dict | list | None = None
    error: str | None = None


@router.get("/workspaces/{workspace_id}/mcp/tools")
def list_tools_route(
    user=Depends(get_current_user),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """List available MCP tools."""
    tools = []
    for name, info in TOOL_REGISTRY.items():
        tools.append({
            "name": name,
            "description": info["description"],
            "params": info["params"],
        })
    return {"tools": tools}


@router.post("/workspaces/{workspace_id}/mcp/call", response_model=MCPToolCallResponse)
def call_tool_route(
    body: MCPToolCallRequest,
    user=Depends(get_current_user),
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """Execute an MCP tool call."""
    tool_info = TOOL_REGISTRY.get(body.tool)
    if not tool_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown tool: {body.tool}",
        )

    # Inject workspace_id (tools always operate within the current workspace)
    params = {**body.params, "workspace_id": ctx.workspace_id}

    try:
        result = tool_info["fn"](**params)
        return MCPToolCallResponse(tool=body.tool, result=result)
    except TypeError as e:
        logger.warning("MCP tool %s parameter error: %s", body.tool, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameters for tool {body.tool}: {e}",
        )
    except Exception as e:
        logger.warning("MCP tool %s execution failed: %s", body.tool, e)
        return MCPToolCallResponse(tool=body.tool, error=str(e))
