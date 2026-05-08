"""
Plan Generator — Breaks user requests into dependency graphs of steps.

Given a user intent and current sheet state, generates a structured plan
that the agent can execute step by step with verification after each batch.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    id: int
    action: str
    params: dict[str, Any]
    depends_on: list[int] = field(default_factory=list)
    description: str = ""


@dataclass
class Plan:
    """A structured execution plan with dependency graph."""
    steps: list[PlanStep]
    estimated_duration_ms: int = 0
    affected_ranges: list[str] = field(default_factory=list)

    def topological_batches(self) -> list[list[PlanStep]]:
        """Group steps into batches where all steps in a batch are independent.
        
        Returns batches in dependency order. Each batch can be executed in parallel.
        """
        completed = set()
        remaining = {step.id: step for step in self.steps}
        batches = []
        
        while remaining:
            batch = [
                step for step in remaining.values()
                if all(dep in completed for dep in step.depends_on)
            ]
            if not batch:
                raise ValueError("Circular dependency detected in plan")
            
            for step in batch:
                completed.add(step.id)
                del remaining[step.id]
            
            batches.append(batch)
        
        return batches


class PlanGenerator:
    """Generates execution plans from user intent + current sheet state."""
    
    async def generate_plan(self, intent: str, snapshot: Any, template: Any = None) -> Plan:
        """Generate a plan from user intent and current state.
        
        Args:
            intent: The user's request (e.g., "Fill out the OPPM for project X")
            snapshot: Current sheet state (text + visual)
            template: Template reference for validation rules
            
        Returns:
            A Plan with dependency-ordered steps
        """
        # TODO: Implement LLM-based plan generation
        # For now, return an empty plan as a stub
        return Plan(steps=[])
