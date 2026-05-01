"""
Stage 2 OCR-Fill service — reads the OCR result produced by ocr_service.py
(Stage 1) and uses the workspace's existing Ollama model to map the detected
form fields to the standard OPPM data schema.

Model assignment
----------------
- Stage 1 (OCR):  gemma4:31b-cloud  (hard-coded in ocr_service.py)
- Stage 2 (Fill): whatever Ollama model is already active in the workspace
                  (resolved via the same _get_models() helper used by
                   oppm_fill_service.py, falling back to gemma4:31b-cloud)
"""

import json
import logging
import re
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.llm import call_with_fallback
from infrastructure.llm.base import ProviderUnavailableError
from domains.analysis.schemas import OcrResult, OcrFillResponse
from domains.analysis.oppm_fill_service import _get_models  # reuse existing model-resolver

logger = logging.getLogger(__name__)

# ── Stage 2 prompt ────────────────────────────────────────────────────────────
_FILL_PROMPT_TEMPLATE = """You are an expert project manager specialised in the One Page Project Manager (OPPM) methodology.

A vision model (Stage 1) has already scanned an uploaded OPPM form image and returned the following OCR data:

=== RAW TEXT EXTRACTED FROM FORM ===
{raw_text}

=== DETECTED FIELD → VALUE PAIRS ===
{fields_json}

=== FORM STRUCTURAL RULES ===
{form_rules_json}

=== CURRENT PROJECT CONTEXT (from the database) ===
Project ID : {project_id}

Your task:
Map the OCR data onto the standard OPPM fill schema below.  Use the OCR values
where they are clearly legible.  Where a field is blank or illegible, leave it
as null.

Return ONLY valid JSON with this exact structure (no commentary outside JSON):
{{
  "fills": {{
    "project_name":          "<string or null>",
    "project_leader":        "<string or null>",
    "start_date":            "<YYYY-MM-DD or null>",
    "deadline":              "<YYYY-MM-DD or null>",
    "project_objective":     "<string or null>",
    "deliverable_output":    "<string or null>",
    "completed_by_text":     "<string or null>",
    "people_count":          "<number as string or null>"
  }},
  "tasks": [
    {{
      "index":    "<e.g. '1' or '1.1'>",
      "title":    "<task or objective title>",
      "deadline": "<YYYY-MM-DD or null>",
      "status":   "<status string or null>",
      "is_sub":   <true|false>,
      "owners":   [],
      "timeline": []
    }}
  ],
  "members": []
}}

Rules:
- Keep fills values concise (under 160 characters each).
- If the form shows no task rows, return tasks as an empty array [].
- Dates must be ISO-8601 (YYYY-MM-DD) or null.
- Do NOT invent data not visible in the OCR output."""


# ── Stage 1 prompt ────────────────────────────────────────────────────────────
_OCR_PROMPT = """You are an expert OCR assistant. Read the uploaded OPPM (One Page Project Manager) form image and extract:
1. All visible text as raw_text
2. Key field-value pairs as a JSON object under "fields"

Return ONLY valid JSON with this exact structure (no commentary outside JSON):
{
  "raw_text": "<all visible text concatenated>",
  "fields": {
    "project_name": "<value or empty>",
    "project_leader": "<value or empty>",
    "start_date": "<YYYY-MM-DD or empty>",
    "deadline": "<YYYY-MM-DD or empty>",
    "project_objective": "<value or empty>",
    "deliverable_output": "<value or empty>",
    "completed_by_text": "<value or empty>",
    "people_count": "<value or empty>"
  }
}"""


async def extract_text_from_upload(
    file_bytes: bytes,
    mime_type: str,
) -> OcrResult:
    """Stage 1 — extract text from an uploaded file using OCR or file parsing.

    Args:
        file_bytes: Raw file bytes.
        mime_type:  MIME type of the uploaded file.

    Returns:
        OcrResult with raw_text and detected fields.
    """
    # For images, use the Ollama vision model
    if mime_type.startswith("image/"):
        from infrastructure.llm.ollama import OllamaAdapter

        adapter = OllamaAdapter()
        result = await adapter.call_vision_json(
            "gemma4:31b-cloud",
            _OCR_PROMPT,
            file_bytes,
        )
        if result is None:
            raise RuntimeError("OCR vision model returned no parseable JSON")

        raw_text = result.get("raw_text", "")
        fields = result.get("fields", {})
        if not isinstance(fields, dict):
            fields = {}
        return OcrResult(raw_text=raw_text, fields=fields)

    # For PDF / XLSX / other files, use the file parser
    from infrastructure.file_parser import parse_file

    parse_result = parse_file(filename="upload", content=file_bytes)
    if parse_result.error:
        raise RuntimeError(f"File parsing failed: {parse_result.error}")

    return OcrResult(
        raw_text=parse_result.text,
        fields={},
    )


async def fill_from_ocr(
    ocr_result: OcrResult,
    session: AsyncSession,
    project_id: str,
    workspace_id: str,
    model_id: str | None = None,
) -> OcrFillResponse:
    """
    Stage 2 — map OCR output to OPPMFillResponse using the workspace's Ollama model.

    Args:
        ocr_result:   Output from ocr_service.extract_text_from_upload().
        session:      Async DB session (used to look up workspace models).
        project_id:   Target project UUID string.
        workspace_id: Target workspace UUID string.
        model_id:     Optional explicit model UUID; otherwise resolved via _get_models().

    Returns:
        OcrFillResponse — same shape as OPPMFillResponse + ocr_raw_text + ocr_fields.
    """
    # Separate __form_rules__ from the regular field dict
    fields_copy = dict(ocr_result.fields)
    form_rules_json = fields_copy.pop("__form_rules__", "{}")

    prompt = _FILL_PROMPT_TEMPLATE.format(
        raw_text=ocr_result.raw_text[:6000],  # guard against huge forms
        fields_json=json.dumps(fields_copy, ensure_ascii=False, indent=2),
        form_rules_json=form_rules_json,
        project_id=project_id,
    )

    # ── Resolve the workspace's existing Ollama model ─────────────────────────
    models = await _get_models(session, workspace_id, model_id)

    # Filter to Ollama-only models for Stage 2 (keep same provider family)
    ollama_models = [m for m in models if m["provider"] == "ollama"]
    if not ollama_models:
        # Fall back to full list if no Ollama models registered
        ollama_models = models

    logger.info(
        "OCR Stage 2: calling fill model %s (provider=%s)",
        ollama_models[0]["model_id"] if ollama_models else "none",
        ollama_models[0]["provider"] if ollama_models else "none",
    )

    response = None
    try:
        response = await call_with_fallback(ollama_models, prompt)
    except ProviderUnavailableError as e:
        logger.warning("OCR Stage 2: all models unavailable: %s", e)
    except Exception as e:
        logger.warning("OCR Stage 2: unexpected error: %s", e)

    # ── Parse the fill model response ─────────────────────────────────────────
    fills: dict[str, str | None] = {
        "project_name": None,
        "project_leader": None,
        "project_leader_member_id": None,
        "start_date": None,
        "deadline": None,
        "project_objective": None,
        "deliverable_output": None,
        "completed_by_text": None,
        "people_count": None,
    }
    tasks: list[dict] = []
    members: list[dict] = []

    if response:
        raw_text = response.text.strip()
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.DOTALL).strip()
        try:
            parsed: dict = json.loads(clean)
            raw_fills = parsed.get("fills", {})
            # Only copy recognised keys
            for key in fills:
                if key in raw_fills:
                    fills[key] = raw_fills[key]
            tasks = parsed.get("tasks", [])
            members = parsed.get("members", [])
        except json.JSONDecodeError:
            logger.warning("OCR Stage 2: fill model returned non-JSON; returning empty fills")

    logger.info(
        "OCR Stage 2 complete: %d fill fields mapped, %d task rows",
        sum(1 for v in fills.values() if v),
        len(tasks),
    )

    return OcrFillResponse(
        fills=fills,
        tasks=tasks,
        members=members,
        ocr_raw_text=ocr_result.raw_text,
        ocr_fields=fields_copy,
    )
