"""
Sheet Verifier — Verifies sheet state after actions.

Compares the current sheet state against expected state after
executing actions, detecting mismatches for replanning.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class SheetVerificationResult:
    """Result of verifying sheet state."""
    passed: bool
    message: str = ""
    expected: Any = None
    actual: Any = None


class SheetVerifier:
    """Verifies sheet state matches expected after actions."""
    
    async def verify_batch(self, batch: list[Any], results: list[Any], snapshot: Any) -> SheetVerificationResult:
        """Verify a batch of executed steps against current sheet state.
        
        Args:
            batch: The steps that were executed
            results: The execution results
            snapshot: Current sheet state after execution
            
        Returns:
            Verification result indicating pass/fail
        """
        # TODO: Implement sheet state verification
        # For now, always pass as a stub
        return SheetVerificationResult(passed=True, message="Verification stub — always passes")
    
    async def verify_border(self, range_str: str, expected_style: str, snapshot: Any) -> SheetVerificationResult:
        """Verify a border matches expected style."""
        actual = snapshot.get_border(range_str) if hasattr(snapshot, 'get_border') else None
        if actual != expected_style:
            return SheetVerificationResult(
                passed=False,
                message=f"Expected {expected_style} border on {range_str}, got {actual}",
                expected=expected_style,
                actual=actual
            )
        return SheetVerificationResult(passed=True, message=f"Border {range_str} matches {expected_style}")
    
    async def verify_value(self, cell: str, expected_value: str, snapshot: Any) -> SheetVerificationResult:
        """Verify a cell value matches expected."""
        actual = snapshot.get_value(cell) if hasattr(snapshot, 'get_value') else None
        if actual != expected_value:
            return SheetVerificationResult(
                passed=False,
                message=f"Expected '{expected_value}' in {cell}, got '{actual}'",
                expected=expected_value,
                actual=actual
            )
        return SheetVerificationResult(passed=True, message=f"Cell {cell} matches '{expected_value}'")
