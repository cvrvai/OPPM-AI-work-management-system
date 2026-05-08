"""
Plan Executor — Executes plans with parallelization and verification.

Executes batches of independent steps in parallel, then verifies
the results before proceeding to the next batch.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from infrastructure.planner.plan_generator import Plan, PlanStep

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a plan step or batch."""
    success: bool
    step_id: int
    output: Any = None
    error: str | None = None


@dataclass
class VerificationResult:
    """Result of verifying a batch of executed steps."""
    passed: bool
    failures: list[ExecutionResult] = None
    
    def __post_init__(self):
        if self.failures is None:
            self.failures = []


class PlanExecutor:
    """Executes plans with parallelization and verification."""
    
    async def execute_plan(self, plan: Plan, execute_fn: Any, verify_fn: Any = None) -> list[ExecutionResult]:
        """Execute a plan step by step with verification after each batch.
        
        Args:
            plan: The plan to execute
            execute_fn: Async function to execute a single step
            verify_fn: Optional async function to verify a batch of results
            
        Returns:
            List of execution results for all steps
        """
        all_results = []
        
        for batch in plan.topological_batches():
            # Execute batch in parallel
            results = await asyncio.gather(*[
                self._execute_step(step, execute_fn)
                for step in batch
            ], return_exceptions=True)
            
            # Convert exceptions to failed results
            processed_results = []
            for step, result in zip(batch, results):
                if isinstance(result, Exception):
                    processed_results.append(ExecutionResult(
                        success=False,
                        step_id=step.id,
                        error=str(result)
                    ))
                else:
                    processed_results.append(result)
            
            all_results.extend(processed_results)
            
            # Verify if verification function provided
            if verify_fn:
                verification = await verify_fn(batch, processed_results)
                if not verification.passed:
                    logger.warning("Batch verification failed: %s", verification.failures)
                    # TODO: Implement replanning logic
        
        return all_results
    
    async def _execute_step(self, step: PlanStep, execute_fn: Any) -> ExecutionResult:
        """Execute a single plan step."""
        try:
            output = await execute_fn(step.action, step.params)
            return ExecutionResult(success=True, step_id=step.id, output=output)
        except Exception as e:
            logger.error("Step %d failed: %s", step.id, e)
            return ExecutionResult(success=False, step_id=step.id, error=str(e))
