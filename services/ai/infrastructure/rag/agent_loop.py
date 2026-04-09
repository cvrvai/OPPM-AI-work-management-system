"""
Agentic tool loop — multi-turn LLM reasoning with tool execution.

Replaces single-shot tool calling. Runs up to MAX_ITERATIONS rounds of:
  LLM call → parse tool calls → execute tools → inject results → repeat
Stops early when the LLM returns no tool calls (natural stopping point).
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.llm import call_with_fallback_tools, NATIVE_TOOL_PROVIDERS
from infrastructure.llm.base import ProviderUnavailableError
from infrastructure.llm.tool_parser import parse_xml_tool_calls
from infrastructure.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5
# Truncate individual tool results to avoid context bloat
_MAX_RESULT_CHARS = 800


@dataclass
class AgentLoopResult:
    """Result from one agentic loop run."""
    final_text: str
    all_tool_results: list[dict[str, Any]] = field(default_factory=list)
    updated_entities: list[str] = field(default_factory=list)
    iterations: int = 0


async def run_agent_loop(
    models: list[dict],
    initial_messages: list[dict],
    registry: ToolRegistry,
    *,
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    user_id: str,
    openai_tools: list[dict] | None = None,
    anthropic_tools: list[dict] | None = None,
    max_iterations: int = MAX_ITERATIONS,
) -> AgentLoopResult:
    """Run the agentic loop until the LLM stops calling tools or max_iterations hit.

    Each iteration:
      1. Call LLM (with tool schemas for native providers; prompt-embedded for others)
      2. Parse tool calls from response (native .tool_calls or XML text)
      3. Execute all tools in this turn
      4. Append tool results as a text message back into the conversation
      5. Repeat

    When no tool calls are returned, the LLM's response is the final answer.
    If max_iterations is reached, one final LLM call is made to get a summary.
    """
    primary_provider = models[0]["provider"] if models else ""
    use_native_tools = primary_provider in NATIVE_TOOL_PROVIDERS

    # Work on a copy so the caller's list is not mutated
    messages: list[dict] = list(initial_messages)

    all_tool_results: list[dict] = []
    all_updated: set[str] = set()

    for iteration in range(max_iterations):
        # ── Call the LLM ──
        try:
            response = await call_with_fallback_tools(
                models,
                messages,
                tools=openai_tools if use_native_tools else None,
                anthropic_tools=anthropic_tools if use_native_tools else None,
            )
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            logger.warning("Agent loop LLM call failed at iteration %d: %s", iteration, exc)
            raise

        # ── Parse tool calls ──
        if response.tool_calls:
            clean_text = response.text.strip()
            raw_calls = response.tool_calls
        else:
            clean_text, raw_calls = parse_xml_tool_calls(response.text)

        # ── No tool calls → final answer ──
        if not raw_calls:
            logger.debug("Agent loop finished after %d iteration(s)", iteration + 1)
            return AgentLoopResult(
                final_text=clean_text,
                all_tool_results=all_tool_results,
                updated_entities=list(all_updated),
                iterations=iteration + 1,
            )

        # ── Execute all tool calls for this turn ──
        turn_results: list[dict] = []
        for tc in raw_calls:
            tool_name = tc.get("tool", "")
            tool_input = tc.get("input", {})
            result = await registry.execute(
                tool_name,
                tool_input,
                session=session,
                project_id=project_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            record = {
                "tool": tool_name,
                "input": tool_input,
                "result": result.result or {},
                "success": result.success,
                "error": result.error,
            }
            turn_results.append(record)
            all_tool_results.append(record)
            if result.updated_entities:
                all_updated.update(result.updated_entities)

        logger.debug(
            "Agent loop iteration %d: executed %d tool(s): %s",
            iteration + 1,
            len(turn_results),
            [r["tool"] for r in turn_results],
        )

        # ── Feed results back: assistant thought + user tool-result turn ──
        # Append what the assistant said (may be empty string if pure tool call)
        messages.append({
            "role": "assistant",
            "content": clean_text or f"[Calling {len(raw_calls)} tool(s)]",
        })

        # Inject tool results as a user message so the LLM can reason over them
        tool_result_text = _format_tool_results(turn_results)
        messages.append({
            "role": "user",
            "content": (
                f"[Tool Results]\n{tool_result_text}\n\n"
                "Using the above results, continue the analysis. "
                "If you have enough information, provide your final answer. "
                "If you still need more data, call the appropriate tools."
            ),
        })

    # ── Max iterations reached — ask for a final wrap-up ──
    logger.debug("Agent loop hit max iterations (%d), requesting final summary", max_iterations)
    messages.append({
        "role": "user",
        "content": "Based on all the information gathered, please provide your final answer now.",
    })
    try:
        final_response = await call_with_fallback_tools(
            models,
            messages,
            tools=openai_tools if use_native_tools else None,
            anthropic_tools=anthropic_tools if use_native_tools else None,
        )
        final_text = final_response.text.strip()
    except Exception as exc:
        logger.warning("Agent loop final summary call failed: %s", exc)
        final_text = "Analysis complete based on gathered data."

    return AgentLoopResult(
        final_text=final_text,
        all_tool_results=all_tool_results,
        updated_entities=list(all_updated),
        iterations=max_iterations,
    )


def _format_tool_results(results: list[dict]) -> str:
    """Render tool execution results as compact readable text for LLM injection."""
    lines: list[str] = []
    for r in results:
        if r["success"]:
            result_str = str(r.get("result", "")).strip()
            if len(result_str) > _MAX_RESULT_CHARS:
                result_str = result_str[:_MAX_RESULT_CHARS] + "... [truncated]"
            lines.append(f"✓ {r['tool']}: {result_str or 'done'}")
        else:
            lines.append(f"✗ {r['tool']}: ERROR — {r.get('error', 'unknown error')}")
    return "\n".join(lines)
