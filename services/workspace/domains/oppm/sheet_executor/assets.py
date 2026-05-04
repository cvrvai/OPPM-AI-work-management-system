"""Sheet action executor — translates OPPM AI JSON actions to Google Sheets API v4 calls.

Supported actions (matching the OPPM AI system prompt contract):
  insert_rows, delete_rows, copy_format, set_border, set_background,
  clear_background, set_text_wrap, set_value, clear_content,
  fill_timeline, clear_timeline, set_owner,
  set_bold, set_text_color, set_note,
  merge_cells, unmerge_cells,
  set_formula, set_number_format, set_alignment,
  set_font_size, set_font_family, set_text_rotation,
  set_row_height, set_column_width,
  freeze_rows, freeze_columns,
  set_conditional_formatting, set_data_validation,
  set_hyperlink,
  protect_range, unprotect_range,
  insert_image, upload_asset_to_drive,
  scaffold_oppm_form

Border styles supported: NONE, DOTTED, DASHED, SOLID, SOLID_MEDIUM, SOLID_THICK, DOUBLE.
Per-side overrides (top_*, bottom_*, left_*, right_*, inner_horizontal_*, inner_vertical_*)
allow fine-grained border control. style=NONE removes borders entirely.
"""

import logging
import mimetypes
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Local asset → Drive upload (Option A image embedding) ──────────────────
#
# Resolves the project's `assets/` folder so the AI can reference local files
# (e.g. "OPPM NHRS.png") and the backend uploads them to the service account's
# Drive on demand, then embeds via =IMAGE(). Override with OPPM_ASSETS_DIR env
# var if the layout ever changes.

_DEFAULT_ASSETS_DIR = Path(__file__).resolve().parents[4] / "assets"
_ASSETS_DIR = Path(os.environ.get("OPPM_ASSETS_DIR") or _DEFAULT_ASSETS_DIR).resolve()

# Cache of (asset_filename, mtime_ns) -> {"file_id": ..., "url": ...}.
# Avoids re-uploading the same file every scaffold call. mtime invalidates the
# cache automatically when the user edits the asset.
_ASSET_DRIVE_CACHE: dict[tuple[str, int], dict[str, str]] = {}

_ALLOWED_IMAGE_MIME_PREFIX = "image/"


def _resolve_safe_asset_path(asset_filename: str) -> Path:
    """Resolve `asset_filename` inside the assets/ dir, rejecting path traversal."""
    if not asset_filename or not isinstance(asset_filename, str):
        raise ValueError("asset_filename is required")
    # Strip surrounding whitespace / quotes (defensive — AI sometimes wraps args)
    name = asset_filename.strip().strip('"').strip("'")
    if not name:
        raise ValueError("asset_filename is empty")
    # Reject anything that smells like a traversal or absolute path
    if name.startswith(("/", "\\")) or ":" in name or ".." in name.replace("\\", "/").split("/"):
        raise ValueError(f"asset_filename must be a plain filename (no path traversal): {asset_filename!r}")
    candidate = (_ASSETS_DIR / name).resolve()
    # Final containment check: candidate must live inside the assets dir
    try:
        candidate.relative_to(_ASSETS_DIR)
    except ValueError:
        raise ValueError(f"asset_filename resolves outside assets dir: {asset_filename!r}")
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"Asset not found: {name} (looked in {_ASSETS_DIR})")
    return candidate


def _upload_local_asset_to_drive(sa_info: dict[str, Any] | None, asset_filename: str) -> dict[str, str]:
    """Upload a local asset to the service account's Drive, share it publicly,
    and return {file_id, url}. Caches by (filename, mtime) to avoid re-uploads.

    Raises ValueError on bad asset name, FileNotFoundError on missing file,
    RuntimeError on Drive errors (caller logs and degrades gracefully).
    """
    if sa_info is None:
        raise RuntimeError("Service account credentials unavailable — cannot upload to Drive")

    path = _resolve_safe_asset_path(asset_filename)
    mtime_ns = path.stat().st_mtime_ns
    cache_key = (path.name, mtime_ns)
    cached = _ASSET_DRIVE_CACHE.get(cache_key)
    if cached:
        logger.debug("upload_asset: cache hit for %s", path.name)
        return cached

    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type or not mime_type.startswith(_ALLOWED_IMAGE_MIME_PREFIX):
        raise ValueError(f"Asset is not a recognised image (mime={mime_type!r}): {path.name}")

    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise RuntimeError("googleapiclient.http is required for Drive uploads") from exc

    # Lazy import keeps this module's top-level imports lean.
    from domains.oppm.google_sheets.credentials import _build_drive_service

    drive = _build_drive_service(sa_info)
    media = MediaFileUpload(str(path), mimetype=mime_type, resumable=False)
    created = drive.files().create(
        body={"name": path.name},
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    file_id = created["id"]

    # Make publicly readable so =IMAGE() can fetch it from Google's servers
    drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
        supportsAllDrives=True,
    ).execute()

    public_url = f"https://drive.google.com/uc?export=view&id={file_id}"
    result = {"file_id": file_id, "url": public_url, "asset_filename": path.name, "mime_type": mime_type}
    _ASSET_DRIVE_CACHE[cache_key] = result
    logger.info("upload_asset: %s → %s", path.name, file_id)
    return result

