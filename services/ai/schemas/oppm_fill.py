"""Schemas for AI OPPM fill endpoint."""

from pydantic import BaseModel
from typing import Optional


class OPPMFillRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_id: Optional[str] = None


class OPPMFillResponse(BaseModel):
    fills: dict[str, Optional[str]]
    """
    Keys returned:
      project_name, project_leader, start_date, deadline,
      project_objective, deliverable_output
    """
