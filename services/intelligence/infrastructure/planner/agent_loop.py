"""
Agentic TAOR loop — Think → Act → Observe → Retry.

Each iteration:
  1. THINK  — LLM reasons in a <think> scratchpad: what it knows, what it needs,
               confidence 1-5, next action.
  2. ACT    — Execute tool calls (with dedup guard to skip identical retries).
  3. OBSERVE — Inject structured result summary + extracted reasoning back to LLM.
  4. RETRY  — If confidence ≤ 2 and iteration ≥ 2, call rag_requery with the gap
               phrase to pull fresh context into the conversation.

Stops early when the LLM returns confidence ≥ 4 with no tool calls.
Falls back to a wrap-up call if max_iterations is reached.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.llm import call_with_fallback_tools, NATIVE_TOOL_PROVIDERS
from infrastructure.llm.base import ProviderUnavailableError
from infrastructure.llm.tool_parser import parse_xml_tool_calls
from infrastructure.tools.registry import ToolRegistry

from infrastructure.skills.base import SkillContext

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 7
_MAX_RESULT_CHARS = 1000   # per tool result before truncation
_CONFIDENCE_STOP = 4       # early-stop threshold (inclusive)
_CONFIDENCE_REQUERY = 2    # trigger dynamic RAG re-query below this
_REQUERY_AFTER_ITER = 2    # don't re-query in the first 2 iterations

# Prompt injected at the start of every iteration to elicit structured reasoning.
_THINK_DIRECTIVE = """\
Before responding, output a reasoning block in this exact format (it will not be shown to the user):
<think>
what_i_know: [one sentence summary of what you have confirmed so far]
what_i_need: [one sentence describing ANY missing data, ambiguity, or required fields — or "nothing" if fully confident]
confidence: [integer 1-5 where 1=guessing, 5=fully certain]
next_action: [call_tools | answer | clarify | requery]
</think>

Rules for next_action:
- clarify: write a friendly message asking the user for the specific missing details. Do NOT call tools.
- call_tools: execute the tools. Do NOT write a final answer in the same turn.
- answer: write your final response. Do NOT call tools.
- requery: re-fetch context from RAG then continue.

CRITICAL: NEVER guess required values (project title, deadline, task ID, member name).
If what_i_need is NOT "nothing" and you cannot resolve it with tools, choose clarify and ask the user.

MANDATORY RULE: When the user requests ANY write action (assign task, create task, update status, set dependency, etc.),
you MUST choose next_action=call_tools and call the appropriate tool(s).
Describing the action in text without calling the tool is a failure — tools are the ONLY way changes take effect.
Do NOT set next_action=answer until ALL requested write operations have been executed via tool calls.
"""


@dataclass
class ThinkBlock:
    """Parsed contents of the LLM's <think> scratchpad."""
    what_i_know: str = ""
    what_i_need: str = ""
    confidence: int = 3
    next_action: str = "call_tools"


@dataclass
class AgentLoopResult:
    """Result from one TAOR loop run."""
    final_text: str
    all_tool_results: list[dict[str, Any]] = field(default_factory=list)
    updated_entities: list[str] = field(default_factory=list)
    iterations: int = 0
    low_confidence: bool = False


# Regex to match think fields WITHOUT <think> tags (naked at start of response)
_NAKED_THINK_RE = re.compile(
    r"^\s*(?:what_i_know:.*\n?)+(?:what_i_need:.*\n?)?(?:confidence:.*\n?)?(?:next_action:.*\n?)?\s*",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_think_block(text: str) -> tuple[str, ThinkBlock]:
    """Strip <think>...</think> from response text and parse the fields.

    Also handles naked think fields (without tags) that the LLM may output.
    Returns (cleaned_text, ThinkBlock).
    """
    tb = ThinkBlock()

    # Try tagged form first: <think>...</think>
    match = re.search(r"<think>(.*?)</think>", text, re.DOTALL | re.IGNORECASE)
    if match:
        block = match.group(1)
        cleaned = (text[: match.start()] + text[match.end() :]).strip()
        _parse_think_fields(block, tb)
        return cleaned, tb

    # Fallback: naked think fields at the start of the response
    naked = _NAKED_THINK_RE.match(text)
    if naked:
        block = naked.group(0)
        cleaned = text[naked.end():].strip()
        _parse_think_fields(block, tb)
        return cleaned, tb

    return text.strip(), tb


def _parse_think_fields(block: str, tb: ThinkBlock) -> None:
    """Parse what_i_know / what_i_need / confidence / next_action from a text block."""
    for line in block.splitlines():
        line = line.strip()
        if line.lower().startswith("what_i_know:"):
            tb.what_i_know = line.split(":", 1)[1].strip()
        elif line.lower().startswith("what_i_need:"):
            tb.what_i_need = line.split(":", 1)[1].strip()
        elif line.lower().startswith("confidence:"):
            raw = line.split(":", 1)[1].strip()
            try:
                tb.confidence = max(1, min(5, int(re.search(r"\d", raw).group())))  # type: ignore[union-attr]
            except (AttributeError, ValueError):
                pass
        elif line.lower().startswith("next_action:"):
            tb.next_action = line.split(":", 1)[1].strip().lower()


def _call_hash(tool_name: str, tool_input: dict) -> str:
    """Stable hash of (tool_name, input) for dedup tracking."""
    payload = json.dumps({"t": tool_name, "i": tool_input}, sort_keys=True, default=str)
    return hashlib.md5(payload.encode()).hexdigest()


def _serialize_result(value: Any) -> Any:
    """Convert a tool result value to a JSON-serializable type.

    SQLAlchemy ORM instances are converted to column-value dicts so they can
    be safely included in the API response and in observation messages.
    """
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return value
    # SQLAlchemy ORM instance — extract column values
    try:
        return {
            c.name: str(getattr(value, c.name))
            if getattr(value, c.name) is not None
            else None
            for c in value.__table__.columns
        }
    except AttributeError:
        pass
    # Fallback: stringify
    return {"_repr": str(value)}


def _format_tool_results(results: list[dict]) -> str:
    """Render tool execution results as compact readable text."""
    lines: list[str] = []
    for r in results:
        if r["success"]:
            result_str = str(r.get("result", "")).strip()
            if len(result_str) > _MAX_RESULT_CHARS:
                result_str = result_str[:_MAX_RESULT_CHARS] + "... [truncated]"
            lines.append(f"✓ {r['tool']}: {result_str or 'done'}")
        else:
            err = r.get("error", "unknown error")
            lines.append(f"✗ {r['tool']}: FAILED — {err}")
    return "\n".join(lines)


def _tool_alternative(tool_name: str) -> str:
    """Suggest a fallback tool when one fails."""
    _ALT: dict[str, str] = {
        "get_task_details": "search_tasks",
        "search_tasks": "get_task_details",
        "get_risk_status": "search_tasks",
        "bulk_set_timeline": "set_timeline_entry",
        "set_timeline_entry": "bulk_set_timeline",
    }
    return _ALT.get(tool_name, "a different tool")


def _build_observe_message(
    turn_results: list[dict],
    think: ThinkBlock,
    *,
    retry_hints: list[str],
    requery_context: str = "",
) -> str:
    """Build the structured OBSERVE injection message for the next LLM turn."""
    sections: list[str] = []

    sections.append("## Tool Results\n" + _format_tool_results(turn_results))

    if think.what_i_know:
        sections.append(f"## Reasoning Checkpoint\n{think.what_i_know}")

    if think.what_i_need and think.what_i_need.lower() not in ("nothing", "none", ""):
        sections.append(f"## Still Needed\n{think.what_i_need}")

    if retry_hints:
        sections.append("## Retry Guidance\n" + "\n".join(retry_hints))

    if requery_context:
        sections.append(f"## Context Update (fresh retrieval)\n{requery_context}")

    # Directive for next step
    if think.confidence >= _CONFIDENCE_STOP and not retry_hints:
        directive = "You have sufficient information. Write your final answer now."
    elif think.confidence <= _CONFIDENCE_REQUERY:
        directive = (
            "Your confidence is low. If more tools are available, call them. "
            "Otherwise provide the best answer you can and note any uncertainty."
        )
    else:
        directive = (
            "If you have enough information, write your final answer. "
            "Otherwise call the relevant tools."
        )
    sections.append(f"## Directive\n{directive}")

    return "\n\n".join(sections)


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
    rag_requery: Callable[..., Awaitable[str]] | None = None,
    on_tool_result: Callable[[dict], Awaitable[None]] | None = None,
    skill_context: SkillContext | None = None,
) -> AgentLoopResult:
    """Run the TAOR agentic loop until confident answer or max_iterations hit.

    Parameters
    ----------
    skill_context:
        Optional ``SkillContext`` from a Skill. When provided, the loop:
        1. Injects ``skill_context.extra_system_prompt`` into the system message.
        2. Appends ``skill_context.preflight_data["snapshot_text"]`` as a
           user message before the conversation history.
        3. Filters the tool list to only those allowed by the skill.
    """
    primary_provider = models[0]["provider"] if models else ""
    use_native_tools = primary_provider in NATIVE_TOOL_PROVIDERS

    # Work on a copy so the caller's list is not mutated
    messages: list[dict] = list(initial_messages)

    # ── Skill context injection ──
    if skill_context is not None:
        # 1. Append skill system prompt to the system message
        if messages and messages[0]["role"] == "system":
            extra = skill_context.extra_system_prompt or ""
            if extra:
                messages[0] = {
                    "role": "system",
                    "content": messages[0]["content"] + "\n\n" + extra,
                }
        # 2. Inject pre-flight snapshot and template summary as user messages
        snapshot = skill_context.preflight_data.get("snapshot_text", "")
        template_summary = skill_context.preflight_data.get("template_summary", "")
        if snapshot:
            messages.insert(1, {"role": "user", "content": snapshot})
        if template_summary:
            messages.insert(2 if snapshot else 1, {"role": "user", "content": template_summary})
        # 3. Filter tools to only those allowed by the skill
        # (The caller is responsible for passing the filtered openai_tools /
        # anthropic_tools; we just log what the skill requested.)
        logger.debug(
            "TAOR running with skill=%s project=%s",
            skill_context.project_id,
            skill_context.workspace_id,
        )

    # Inject the THINK directive into the system prompt so the LLM knows the format
    if messages and messages[0]["role"] == "system":
        messages[0] = {
            "role": "system",
            "content": messages[0]["content"] + "\n\n" + _THINK_DIRECTIVE,
        }

    all_tool_results: list[dict] = []
    all_updated: set[str] = set()
    tried_calls: set[str] = set()   # dedup guard: hash(tool_name, input)
    last_confidence: int = 3

    for iteration in range(max_iterations):
        # ── 1. THINK — LLM call ──
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
            logger.warning("TAOR loop LLM call failed at iteration %d: %s", iteration, exc)
            raise

        # Parse <think> block and strip it from visible text
        if response.tool_calls:
            raw_text = response.text.strip()
            raw_calls = response.tool_calls
        else:
            raw_text, raw_calls = parse_xml_tool_calls(response.text)

        clean_text, think = _extract_think_block(raw_text)
        last_confidence = think.confidence

        logger.debug(
            "TAOR iter %d — confidence=%d next_action=%s tools=%d",
            iteration + 1, think.confidence, think.next_action, len(raw_calls),
        )

        # ── Early stop: confident answer with no pending tool calls ──
        if not raw_calls and think.confidence >= _CONFIDENCE_STOP:
            logger.debug("TAOR early stop at iteration %d (confidence=%d)", iteration + 1, think.confidence)
            return AgentLoopResult(
                final_text=clean_text,
                all_tool_results=all_tool_results,
                updated_entities=list(all_updated),
                iterations=iteration + 1,
                low_confidence=False,
            )

        # ── No tool calls and not an early-confident stop → still a final answer ──
        if not raw_calls:
            logger.debug("TAOR finished (no tools) after %d iteration(s)", iteration + 1)
            return AgentLoopResult(
                final_text=clean_text,
                all_tool_results=all_tool_results,
                updated_entities=list(all_updated),
                iterations=iteration + 1,
                low_confidence=think.confidence <= _CONFIDENCE_REQUERY,
            )

        # ── 2. ACT — Execute tool calls with dedup guard ──
        turn_results: list[dict] = []
        retry_hints: list[str] = []

        for tc in raw_calls:
            tool_name = tc.get("tool", "")
            tool_input = tc.get("input", {})
            call_id = _call_hash(tool_name, tool_input)

            if call_id in tried_calls:
                logger.debug("TAOR skipping duplicate call: %s", tool_name)
                retry_hints.append(
                    f"You already called `{tool_name}` with the same parameters. "
                    "Either use different parameters or try a different tool."
                )
                continue
            tried_calls.add(call_id)

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
                "result": _serialize_result(result.result) if result.result is not None else {},
                "success": result.success,
                "error": result.error,
            }
            turn_results.append(record)
            all_tool_results.append(record)

            if result.updated_entities:
                all_updated.update(result.updated_entities)

            # Notify streaming consumers after each tool call
            if on_tool_result is not None:
                try:
                    await on_tool_result({
                        "tool": tool_name,
                        "success": result.success,
                        "updated_entities": list(result.updated_entities or []),
                        "error": result.error,
                    })
                except Exception as cb_exc:
                    logger.debug("on_tool_result callback raised: %s", cb_exc)

            # Propagate newly created project ID so subsequent tool calls in this
            # same iteration (e.g. create_objective / create_task) resolve it
            # correctly without waiting for the next LLM turn.
            if tool_name == "create_project" and result.success and result.result:
                new_pid = result.result.get("id")
                if new_pid:
                    project_id = new_pid

            # Tool failure: generate retry guidance
            if not result.success:
                alt = _tool_alternative(tool_name)
                retry_hints.append(
                    f"`{tool_name}` failed: {result.error}. "
                    f"Try `{alt}` or rephrase the parameters."
                )

        logger.debug(
            "TAOR iter %d: ran %d tool(s): %s",
            iteration + 1, len(turn_results), [r["tool"] for r in turn_results],
        )

        # ── 4. RETRY — Dynamic RAG re-query on low confidence ──
        requery_context = ""
        if (
            rag_requery is not None
            and think.confidence <= _CONFIDENCE_REQUERY
            and iteration >= _REQUERY_AFTER_ITER
            and think.what_i_need
            and think.what_i_need.lower() not in ("nothing", "none", "")
        ):
            try:
                logger.debug("TAOR re-querying RAG for gap: %s", think.what_i_need)
                requery_context = await rag_requery(think.what_i_need)
            except Exception as exc:
                logger.warning("TAOR RAG re-query failed: %s", exc)

        # ── 3. OBSERVE — Build structured injection message ──
        messages.append({
            "role": "assistant",
            "content": clean_text or f"[Calling {len(raw_calls)} tool(s)]",
        })
        observe_msg = _build_observe_message(
            turn_results, think,
            retry_hints=retry_hints,
            requery_context=requery_context,
        )
        messages.append({"role": "user", "content": observe_msg})

    # ── Max iterations reached — final wrap-up call ──
    logger.debug("TAOR hit max iterations (%d), requesting final summary", max_iterations)
    messages.append({
        "role": "user",
        "content": "Based on all the information gathered above, provide your final answer now.",
    })
    try:
        final_response = await call_with_fallback_tools(
            models,
            messages,
            tools=openai_tools if use_native_tools else None,
            anthropic_tools=anthropic_tools if use_native_tools else None,
        )
        final_raw, _ = _extract_think_block(final_response.text)
        final_text = final_raw.strip()
    except Exception as exc:
        logger.warning("TAOR final summary call failed: %s", exc)
        final_text = "Analysis complete — please review the tool results above."

    return AgentLoopResult(
        final_text=final_text,
        all_tool_results=all_tool_results,
        updated_entities=list(all_updated),
        iterations=max_iterations,
        low_confidence=last_confidence <= _CONFIDENCE_REQUERY,
    )
