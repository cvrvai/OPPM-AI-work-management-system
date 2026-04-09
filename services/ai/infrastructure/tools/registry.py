"""Tool registry — central hub for registering, discovering, and executing AI tools."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.tools.base import ToolDefinition, ToolParam, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Singleton registry for all AI-callable tools.

    Supports:
      - register() / get_tool() / get_tools()
      - execute() — runs a tool by name
      - to_openai_schema() — native OpenAI function calling format
      - to_anthropic_schema() — native Anthropic tool_use format
      - to_prompt_text() — markdown for prompt-based tool calling (Ollama, Kimi)
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            logger.warning("Tool '%s' already registered — overwriting", tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s (%s)", tool.name, tool.category)

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_tools(
        self,
        category: str | None = None,
        requires_project: bool | None = None,
    ) -> list[ToolDefinition]:
        tools = list(self._tools.values())
        if category is not None:
            tools = [t for t in tools if t.category == category]
        if requires_project is not None:
            tools = [t for t in tools if t.requires_project == requires_project]
        return tools

    async def execute(
        self,
        name: str,
        tool_input: dict[str, Any],
        *,
        session: AsyncSession,
        project_id: str,
        workspace_id: str,
        user_id: str,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Unknown tool: {name}")

        try:
            result = await tool.handler(
                session=session,
                tool_input=tool_input,
                project_id=project_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            return result
        except Exception as e:
            logger.warning("Tool '%s' execution failed: %s", name, e)
            return ToolResult(success=False, error=str(e))

    # ── Schema generation for native LLM function calling ──

    def _param_to_json_schema(self, p: ToolParam) -> dict:
        schema: dict[str, Any] = {
            "type": p.type,
            "description": p.description,
        }
        if p.enum:
            schema["enum"] = p.enum
        if p.type == "array" and p.items_type:
            schema["items"] = {"type": p.items_type}
        return schema

    def to_openai_schema(self, category: str | None = None) -> list[dict]:
        """Generate OpenAI-compatible function definitions."""
        tools = self.get_tools(category=category)
        result = []
        for t in tools:
            properties = {}
            required = []
            for p in t.params:
                properties[p.name] = self._param_to_json_schema(p)
                if p.required:
                    required.append(p.name)

            result.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
        return result

    def to_anthropic_schema(self, category: str | None = None) -> list[dict]:
        """Generate Anthropic-compatible tool definitions."""
        tools = self.get_tools(category=category)
        result = []
        for t in tools:
            properties = {}
            required = []
            for p in t.params:
                properties[p.name] = self._param_to_json_schema(p)
                if p.required:
                    required.append(p.name)

            result.append({
                "name": t.name,
                "description": t.description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
        return result

    def to_prompt_text(self, category: str | None = None) -> str:
        """Generate markdown tool descriptions for prompt-based calling."""
        tools = self.get_tools(category=category)
        if not tools:
            return ""

        lines = [
            "## Available Tools",
            'When the user wants to make changes, include a JSON tool_calls array at the END of your message inside <tool_calls>...</tool_calls> tags.',
            "",
            "Available tools:",
        ]

        for t in tools:
            param_parts = []
            for p in t.params:
                if p.enum:
                    val = f'"{"|".join(p.enum)}"'
                elif p.type == "string":
                    val = '"..."'
                elif p.type in ("integer", "number"):
                    val = "N"
                elif p.type == "boolean":
                    val = "true|false"
                elif p.type == "array":
                    val = "[...]"
                else:
                    val = "..."
                marker = "" if p.required else " (optional)"
                param_parts.append(f'"{p.name}": {val}{marker}')
            params_str = ", ".join(param_parts)
            lines.append(f"- {t.name}: {{{{{params_str}}}}}")
            lines.append(f"  Description: {t.description}")

        lines.extend([
            "",
            "Example:",
            "<tool_calls>",
            '[{{"tool": "tool_name", "input": {{"param": "value"}}}}]',
            "</tool_calls>",
        ])
        return "\n".join(lines)


# ── Global singleton ──
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get (or create) the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_all_tools(_registry)
    return _registry


def _register_all_tools(registry: ToolRegistry) -> None:
    """Import and register all tool modules."""
    from infrastructure.tools import oppm_tools    # noqa: F401
    from infrastructure.tools import task_tools    # noqa: F401
    from infrastructure.tools import cost_tools    # noqa: F401
    from infrastructure.tools import read_tools    # noqa: F401
    from infrastructure.tools import project_tools # noqa: F401
