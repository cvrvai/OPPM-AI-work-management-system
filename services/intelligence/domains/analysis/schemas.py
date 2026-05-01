"""Schemas for the two-stage OCR → AI form-fill pipeline endpoint."""

from typing import Optional
from pydantic import BaseModel
from domains.analysis.oppm_fill_schemas import OPPMFillResponse


class OcrResult(BaseModel):
    """Structured output from Stage 1 (OCR model)."""
    raw_text: str
    fields: dict[str, str] = {}


class OcrFillResponse(OPPMFillResponse):
    """
    Response returned by POST /ai/ocr-fill.

    Extends the standard OPPMFillResponse with the raw OCR artefacts so the
    frontend can show the user what the OCR model detected before applying.
    """
    ocr_raw_text: str = ""
    ocr_fields: dict[str, str] = {}
