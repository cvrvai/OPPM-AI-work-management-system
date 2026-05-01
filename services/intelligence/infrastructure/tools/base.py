"""Tool definition types for the AI tool registry."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ToolParam:
    """Schema for a single tool parameter."""
    name: str
    type: str  # "string", "integer", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    enum: list[str] | None = None
    items_type: str | None = None  # for array params


@dataclass
class ToolDefinition:
    """Complete definition of an AI-callable tool."""
    name: str
    description: str
    category: str  # "oppm", "task", "cost", "read", "analysis"
    params: list[ToolParam]
    handler: Callable[..., Awaitable[dict[str, Any]]]
    requires_project: bool = True


@dataclass
class ToolResult:
    """Result from executing a tool."""
    success: bool
    result: Any = None
    error: str | None = None
    updated_entities: list[str] = field(default_factory=list)
