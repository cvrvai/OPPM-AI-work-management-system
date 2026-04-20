"""GraphQL schema definitions using Strawberry for AI service queries and mutations."""
from typing import Optional
import strawberry


@strawberry.type
class StatusItem:
    """Status item for project tracking."""
    title: str
    description: Optional[str] = None


@strawberry.type
class WeeklySummaryResult:
    """Weekly project status summary with categorized updates."""
    summary: str
    at_risk: list["StatusItem"]
    on_track: list["StatusItem"]
    blocked: list["StatusItem"]
    suggested_actions: list["StatusItem"]


@strawberry.type
class SuggestedObjective:
    """Suggested OPPM objective from AI planning."""
    title: str
    suggested_weeks: list[str]


@strawberry.type
class SuggestPlanResult:
    """Result of AI plan suggestion containing objectives and explanation."""
    suggested_objectives: list[SuggestedObjective]
    explanation: str
    commit_token: str
