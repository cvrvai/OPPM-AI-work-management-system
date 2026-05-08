"""
Skill Improver — Automatically updates skill prompts based on feedback.

Analyzes user corrections and suggests prompt patches to prevent
repeated mistakes. Requires human review before applying patches in production.
"""

import logging
from dataclasses import dataclass
from typing import Any

from infrastructure.learning.feedback_memory import Correction

logger = logging.getLogger(__name__)


@dataclass
class PromptPatch:
    """A suggested patch to a skill's system prompt."""
    skill_name: str
    original_text: str
    replacement_text: str
    reason: str


class SkillImprover:
    """Automatically improves skills based on user feedback."""
    
    def __init__(self, llm: Any = None):
        self.llm = llm
    
    async def improve_skill(self, skill: Any, corrections: list[Correction]) -> list[PromptPatch]:
        """Generate prompt patches from user corrections.
        
        Args:
            skill: The skill to improve
            corrections: List of user corrections
            
        Returns:
            List of suggested prompt patches
        """
        if not corrections or not self.llm:
            return []
        
        logger.info("Generating patches for skill %s from %d corrections", 
                     skill.name if hasattr(skill, 'name') else 'unknown', len(corrections))
        
        # TODO: Implement LLM-based patch generation
        # For now, return empty list as a stub
        return []
    
    async def apply_patch(self, skill: Any, patch: PromptPatch) -> bool:
        """Apply a patch to a skill's system prompt.
        
        WARNING: In production, this should require human review.
        
        Args:
            skill: The skill to patch
            patch: The patch to apply
            
        Returns:
            True if patch was applied successfully
        """
        if not hasattr(skill, 'system_prompt'):
            logger.error("Skill does not have a system_prompt attribute")
            return False
        
        if patch.original_text not in skill.system_prompt:
            logger.error("Original text not found in skill prompt")
            return False
        
        skill.system_prompt = skill.system_prompt.replace(
            patch.original_text,
            patch.replacement_text
        )
        
        logger.info("Applied patch to skill %s: %s", 
                     skill.name if hasattr(skill, 'name') else 'unknown', patch.reason)
        return True
    
    def generate_patch_diff(self, patch: PromptPatch) -> str:
        """Generate a human-readable diff of a patch.
        
        Args:
            patch: The patch to diff
            
        Returns:
            Formatted diff text
        """
        return f"""
--- {patch.skill_name} ---
Reason: {patch.reason}

- {patch.original_text}
+ {patch.replacement_text}
"""
