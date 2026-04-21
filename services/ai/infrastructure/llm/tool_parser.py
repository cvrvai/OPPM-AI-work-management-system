"""Tool call parsers — extract tool calls from LLM responses across providers."""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_xml_tool_calls(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract tool_calls JSON from XML tags in LLM response.

    Used for prompt-based tool calling (Ollama, Kimi, or any provider
    that doesn't support native function calling).

    Returns (clean_response_text, list_of_tool_calls).
    """
    match = re.search(r"<tool_calls>\s*(.*?)\s*</tool_calls>", text, re.DOTALL)
    if not match:
        return text.strip(), []

    clean_text = text[:match.start()].strip()
    try:
        calls = json.loads(match.group(1))
        if isinstance(calls, list):
            return clean_text, calls
    except json.JSONDecodeError:
        logger.warning("Failed to parse tool_calls JSON from LLM response")

    return clean_text, []


def parse_openai_tool_calls(response_data: dict) -> tuple[str, list[dict[str, Any]]]:
    """Parse tool calls from OpenAI's native function calling response.

    Args:
        response_data: The full API response JSON.

    Returns (assistant_text, list_of_tool_calls) in unified format.
    """
    message = response_data["choices"][0]["message"]
    text = message.get("content") or ""
    tool_calls_raw = message.get("tool_calls", [])

    calls = []
    for tc in tool_calls_raw:
        if tc.get("type") == "function":
            fn = tc["function"]
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            calls.append({
                "tool": fn["name"],
                "input": args,
                "call_id": tc.get("id"),
            })

    return text.strip(), calls


def parse_anthropic_tool_calls(response_data: dict) -> tuple[str, list[dict[str, Any]]]:
    """Parse tool calls from Anthropic's tool_use response.

    Args:
        response_data: The full API response JSON.

    Returns (assistant_text, list_of_tool_calls) in unified format.
    """
    content_blocks = response_data.get("content", [])
    text_parts = []
    calls = []

    for block in content_blocks:
        if block["type"] == "text":
            text_parts.append(block["text"])
        elif block["type"] == "tool_use":
            calls.append({
                "tool": block["name"],
                "input": block.get("input", {}),
                "call_id": block.get("id"),
            })

    return "\n".join(text_parts).strip(), calls
