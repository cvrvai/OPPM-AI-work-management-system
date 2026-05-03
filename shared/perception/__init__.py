"""Perception layer — shared structured understanding of sheet state and templates.

Accessible to all services (workspace, intelligence, integrations, automation).
"""

from .template_reference import TemplateReference

__all__ = ["TemplateReference"]
