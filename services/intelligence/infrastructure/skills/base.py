"""Skill base classes.

A `Skill` is a manifest:
  - which tool categories the agent is allowed to call
  - the system prompt that turns the generic agent into a domain specialist
  - an optional pre_flight hook to bulk-load context (saves tool calls)
  - an optional post_flight hook for side effects (e.g. push to Google Sheets)

A `SkillContext` is the concrete data the pre_flight produced for one run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class SkillContext:
    """Per-run data passed to the agent loop.

    `preflight_data` is whatever the skill loaded ahead of time.
    `extra_system_prompt` is appended to the skill's base system prompt.
    """
    project_id: str
    workspace_id: str
    user_id: str
    preflight_data: dict[str, Any] = field(default_factory=dict)
    extra_system_prompt: str = ""


@dataclass
class SkillResult:
    """Return shape from running a skill."""
    final_text: str
    tool_results: list[dict] = field(default_factory=list)
    updated_entities: list[str] = field(default_factory=list)
    iterations: int = 0
    low_confidence: bool = False
    postflight: dict[str, Any] | None = None


PreFlight = Callable[[AsyncSession, SkillContext], Awaitable[dict[str, Any]]]
PostFlight = Callable[[AsyncSession, SkillContext, SkillResult], Awaitable[dict[str, Any]]]


@dataclass
class Skill:
    name: str
    description: str
    tool_categories: list[str]
    extra_tool_names: list[str] = field(default_factory=list)
    system_prompt: str = ""
    triggers: list[str] = field(default_factory=list)
    pre_flight: PreFlight | None = None
    post_flight: PostFlight | None = None

    def matches_trigger(self, text: str) -> bool:
        """Cheap rule-based intent match. The router can use this before
        falling back to an LLM classifier."""
        if not text or not self.triggers:
            return False
        lowered = text.lower()
        return any(trigger.lower() in lowered for trigger in self.triggers)

    def allowed_tool_names(self, all_tools: list) -> set[str]:
        """Names the LLM is allowed to call.

        `all_tools` is the full list of `ToolDefinition` from the registry
        (passed in to avoid an import cycle with infrastructure.tools).
        """
        names: set[str] = set(self.extra_tool_names)
        for tool in all_tools:
            if tool.category in self.tool_categories:
                names.add(tool.name)
        return names


class SkillRegistry:
    """Singleton registry. Today only OPPM_SKILL is registered; future skills
    (task_triage, cost_review, …) plug in here."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        if skill.name in self._skills:
            logger.warning("Skill %r already registered — overwriting", skill.name)
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def pick_by_trigger(self, text: str) -> Skill | None:
        """First skill whose triggers match. None if no match."""
        for skill in self._skills.values():
            if skill.matches_trigger(text):
                return skill
        return None


SKILL_REGISTRY = SkillRegistry()
