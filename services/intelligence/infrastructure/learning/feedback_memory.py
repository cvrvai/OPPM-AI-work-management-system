"""
Feedback Memory — Stores user corrections and injects them into future prompts.

When the AI makes a mistake and the user corrects it, this module stores
the correction and retrieves relevant corrections for future sessions.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Correction:
    """A single user correction to an AI action."""
    skill: str
    context: str
    wrong_action: dict[str, Any]
    correct_action: dict[str, Any]
    reason: str
    workspace_id: str | None = None
    created_at: str | None = None


class FeedbackMemory:
    """Stores and retrieves user corrections for skill improvement."""
    
    def __init__(self, db: Any = None):
        self.db = db
        self._cache: list[Correction] = []
    
    async def store_correction(self, workspace_id: str, correction: Correction) -> None:
        """Store a user correction for future retrieval.
        
        Args:
            workspace_id: The workspace context
            correction: The correction to store
        """
        correction.workspace_id = workspace_id
        
        if self.db:
            # TODO: Persist to database
            logger.info("Storing correction for workspace %s: %s", workspace_id, correction.reason)
        else:
            self._cache.append(correction)
            logger.info("Cached correction for workspace %s: %s", workspace_id, correction.reason)
    
    async def get_relevant_corrections(self, workspace_id: str, intent: str, limit: int = 5) -> list[Correction]:
        """Retrieve corrections relevant to the current intent.
        
        Args:
            workspace_id: The workspace context
            intent: The user's current intent
            limit: Maximum number of corrections to return
            
        Returns:
            List of relevant corrections
        """
        # TODO: Implement semantic search over corrections
        # For now, return all cached corrections for the workspace
        relevant = [
            c for c in self._cache
            if c.workspace_id == workspace_id
        ]
        return relevant[:limit]
    
    def build_correction_prompt(self, corrections: list[Correction]) -> str:
        """Build a prompt snippet from corrections to inject into the system prompt.
        
        Args:
            corrections: List of corrections to include
            
        Returns:
            Formatted prompt text
        """
        if not corrections:
            return ""
        
        lines = ["## Previous Corrections (learn from these):"]
        for i, c in enumerate(corrections, 1):
            lines.append(f"{i}. Context: {c.context}")
            lines.append(f"   Wrong: {c.wrong_action}")
            lines.append(f"   Correct: {c.correct_action}")
            lines.append(f"   Reason: {c.reason}")
        
        return "\n".join(lines)
