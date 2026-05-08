"""
Learning infrastructure — Feedback memory and skill improvement.

Provides the learning layer for the AI agent:
- FeedbackMemory: Stores user corrections and injects them into future prompts
- SkillImprover: Automatically updates skill prompts based on feedback
"""

from infrastructure.learning.feedback_memory import FeedbackMemory
from infrastructure.learning.skill_improver import SkillImprover

__all__ = [
    "FeedbackMemory",
    "SkillImprover",
]
