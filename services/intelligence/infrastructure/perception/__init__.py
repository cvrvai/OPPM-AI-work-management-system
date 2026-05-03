"""Perception layer — gives the AI structured understanding of sheet state and templates.

Re-exports from shared.perception for backward compatibility.
All services should prefer `from shared.perception import TemplateReference`.
"""

from shared.perception import TemplateReference

__all__ = ["TemplateReference"]
