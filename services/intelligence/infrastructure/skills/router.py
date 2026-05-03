"""Skill Router — two-stage classifier that picks the right Skill for a user intent.

Stage A (rule-based, no LLM call):
  - Auto-Fill button → always OPPM_SKILL
  - Chat message contains 2+ trigger keywords from a single skill → that skill

Stage B (LLM fallback, only if Stage A is ambiguous):
  - One small LLM call returning {"skill": "oppm", "confidence": 0.9}
  - Confidence < 0.6 → general_skill (full tool registry, no specialism)

Usage:
    from infrastructure.skills import SKILL_REGISTRY
    from infrastructure.skills.router import pick_skill

    skill = pick_skill("Fill the OPPM form for project X")
    if skill is None:
        skill = GENERAL_SKILL   # fallback
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from infrastructure.llm import call_with_fallback
from infrastructure.llm.base import ProviderUnavailableError
from infrastructure.skills.base import Skill, SkillRegistry, SKILL_REGISTRY

logger = logging.getLogger(__name__)

# ── General Skill (fallback) ────────────────────────────────────────────────

_GENERAL_SYSTEM_PROMPT = """\
You are a general project-management assistant. You can help with tasks,
projects, costs, OPPM forms, and team workload. Use the available tools
when the user asks for changes, and answer conversationally for questions.
"""

GENERAL_SKILL = Skill(
    name="general",
    description="General project-management assistant with full tool access.",
    triggers=[],
    tool_categories=["oppm", "task", "cost", "read", "project", "analysis"],
    extra_tool_names=[],
    system_prompt=_GENERAL_SYSTEM_PROMPT,
    pre_flight=None,
    post_flight=None,
)

# ── Stage A: Rule-based fast path ──────────────────────────────────────────


def _count_trigger_matches(skill: Skill, text: str) -> int:
    """Return how many of the skill's triggers appear in the text."""
    if not text or not skill.triggers:
        return 0
    lowered = text.lower()
    count = 0
    for trigger in skill.triggers:
        if trigger.lower() in lowered:
            count += 1
    return count


def _pick_by_rule(text: str, registry: SkillRegistry) -> Skill | None:
    """Rule-based skill selection. No LLM call.

    Returns the skill with the highest trigger match count.
    Only returns a skill if at least 2 triggers match (reduces false positives).
    """
    best_skill: Skill | None = None
    best_count = 0

    for skill in registry.all():
        count = _count_trigger_matches(skill, text)
        if count > best_count and count >= 2:
            best_count = count
            best_skill = skill

    return best_skill


# ── Stage B: LLM classifier fallback ────────────────────────────────────────

_ROUTER_PROMPT_TEMPLATE = """\
You are a routing classifier. Your job is to pick the best skill for a user message.

Available skills:
{skill_descriptions}

User message: "{user_message}"

Return ONLY a JSON object with exactly these two keys:
{{
  "skill": "<skill_name>",
  "confidence": 0.0 to 1.0
}}

Rules:
- confidence >= 0.8: the message clearly belongs to one skill.
- confidence 0.6–0.79: somewhat ambiguous but a best guess exists.
- confidence < 0.6: fallback to "general".
- Return ONLY the JSON. No markdown fences, no explanation.
"""


async def _pick_by_llm(
    text: str,
    registry: SkillRegistry,
    models: list[dict[str, Any]],
) -> Skill | None:
    """LLM-based skill selection. One small call (~50 tokens out)."""
    skill_descriptions = "\n".join(
        f"- {skill.name}: {skill.description}"
        for skill in registry.all()
    )
    prompt = _ROUTER_PROMPT_TEMPLATE.format(
        skill_descriptions=skill_descriptions,
        user_message=text,
    )

    try:
        response = await call_with_fallback(models, prompt)
    except ProviderUnavailableError:
        logger.warning("Skill router LLM unavailable — falling back to general")
        return None
    except Exception as e:
        logger.warning("Skill router LLM call failed: %s", e)
        return None

    raw_text = response.text.strip()
    # Strip markdown fences
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.DOTALL).strip()

    result: dict | None = None
    try:
        result = json.loads(clean)
    except json.JSONDecodeError:
        # Try to extract a JSON object
        match = re.search(r'\{[^{}]*"skill"[^{}]*\}', raw_text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    if not result:
        logger.debug("Skill router could not parse LLM response: %s", raw_text[:200])
        return None

    skill_name = result.get("skill", "")
    confidence = float(result.get("confidence", 0.0))

    if confidence < 0.6 or skill_name == "general":
        logger.debug("Skill router confidence too low (%.2f) — general fallback", confidence)
        return None

    skill = registry.get(skill_name)
    if skill:
        logger.info("Skill router picked %r via LLM (confidence=%.2f)", skill_name, confidence)
        return skill

    logger.debug("Skill router returned unknown skill %r", skill_name)
    return None


# ── Public API ─────────────────────────────────────────────────────────────


def pick_skill_rule_based(text: str) -> Skill | None:
    """Synchronous rule-based skill picker. Use for deterministic entry points
    like the Auto-Fill button (always OPPM) or when you want zero LLM cost."""
    return _pick_by_rule(text, SKILL_REGISTRY)


async def pick_skill(
    text: str,
    models: list[dict[str, Any]] | None = None,
    *,
    force_skill: str | None = None,
) -> Skill:
    """Two-stage skill router.

    Parameters
    ----------
    text:
        The user message or synthesized intent string.
    models:
        Fallback model list for the LLM classifier stage. If None, Stage B
        is skipped and we fall back to GENERAL_SKILL on ambiguity.
    force_skill:
        If provided, bypass routing and return this skill by name.
        Used by the Auto-Fill button: ``force_skill="oppm"``.

    Returns
    -------
    Skill instance (never None — falls back to GENERAL_SKILL).
    """
    # 1. Forced override (e.g., Auto-Fill button)
    if force_skill:
        skill = SKILL_REGISTRY.get(force_skill)
        if skill:
            logger.info("Skill router forced %r", force_skill)
            return skill
        logger.warning("Skill router forced unknown skill %r — falling back", force_skill)
        return GENERAL_SKILL

    # 2. Stage A — rule-based
    skill = _pick_by_rule(text, SKILL_REGISTRY)
    if skill:
        logger.info("Skill router picked %r via rule-based triggers", skill.name)
        return skill

    # 3. Stage B — LLM classifier (only if models provided)
    if models:
        skill = await _pick_by_llm(text, SKILL_REGISTRY, models)
        if skill:
            return skill

    # 4. Fallback
    logger.debug("Skill router: no match — general fallback")
    return GENERAL_SKILL
