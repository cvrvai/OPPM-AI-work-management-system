"""
Planner infrastructure — Plan generation, execution, and verification.

Provides the planning layer for the AI agent:
- PlanGenerator: Breaks user requests into dependency graphs of steps
- PlanExecutor: Executes plans with parallelization and verification
- SheetVerifier: Verifies sheet state after actions
- AgentLoop: TAOR loop (Think → Act → Observe → Retry)
- Agent: Query classifier and routing
"""

from infrastructure.planner.agent import classify_query
from infrastructure.planner.agent_loop import run_agent_loop

__all__ = [
    "classify_query",
    "run_agent_loop",
]
