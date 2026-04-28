"""MCP service exceptions."""
from shared.exceptions.base import NotFoundError, ValidationError


class ToolNotFoundError(NotFoundError):
    default_message = "MCP tool not found"


class ToolExecutionError(ValidationError):
    default_message = "MCP tool execution failed"
