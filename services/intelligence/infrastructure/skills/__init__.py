"""Skill system — bundles a system prompt + filtered tool list + pre/post-flight hooks.

A skill is a configuration the existing TAOR agent loop runs under, not a separate
agent. Same loop, different prompt + filtered tools + side-effect hooks.

See `docs/architecture/agent-skills-pipeline.md` for the design.
"""

from .base import Skill, SkillContext, SkillResult, SKILL_REGISTRY
from .oppm_skill import OPPM_SKILL
from .router import pick_skill, pick_skill_rule_based, GENERAL_SKILL

# Register concrete skills
SKILL_REGISTRY.register(OPPM_SKILL)

__all__ = [
    "Skill",
    "SkillContext",
    "SkillResult",
    "SKILL_REGISTRY",
    "OPPM_SKILL",
    "GENERAL_SKILL",
    "pick_skill",
    "pick_skill_rule_based",
]
