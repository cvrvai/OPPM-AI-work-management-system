"""Module-level constants for Google Sheets OPPM integration."""

import re

_GOOGLE_SHEET_KEY = "google_sheet"
_GOOGLE_CREDENTIALS_KEY = "google_sheets_credentials"
_OPPM_SHEET_TITLE = "OPPM"
_SUMMARY_SHEET_TITLE = "OPPM Summary"
_TASKS_SHEET_TITLE = "OPPM Tasks"
_MEMBERS_SHEET_TITLE = "OPPM Members"
_SPREADSHEET_URL_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
_SPREADSHEET_ID_RE = re.compile(r"^[a-zA-Z0-9-_]{20,}$")
_GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
    # drive.file lets the service account CREATE files in its own Drive and
    # manage permissions on those files. Required for uploading user-supplied
    # images (e.g. OPPM matrix-center diagram) that the sheet then embeds via
    # =IMAGE(). Narrower than full drive scope — SA can only touch files it
    # owns, not the user's other Drive content.
    "https://www.googleapis.com/auth/drive.file",
]
_XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_CLASSIC_MAX_TASK_ROWS = 64
_CLASSIC_VISIBLE_TASK_ROWS = 16
_DEFAULT_LAYOUT_SCAN_RANGE = "A1:AZ120"
_CLASSIC_SUB_OBJECTIVE_COLUMNS = 6
_SUMMARY_BLOCK_FIELDS = ("project_objective", "deliverable_output", "start_date", "deadline")
_INLINE_LABEL_FIELDS = {"project_leader", "project_name", "completed_by"}
_VALUE_LABEL_FIELDS = {"project_objective", "deliverable_output", "start_date", "deadline"}
_EXPLICIT_MAPPING_SCALAR_FIELDS = (*sorted(_INLINE_LABEL_FIELDS), *_VALUE_LABEL_FIELDS)
_EXPLICIT_MAPPING_FIELD_IDS = set(_EXPLICIT_MAPPING_SCALAR_FIELDS) | {"task_anchor"}
_SUMMARY_HELPER_LABELS = (
    ("Project Name", "project_name"),
    ("Project Leader", "project_leader"),
    ("Leader Member ID", "project_leader_member_id"),
    ("People Count", "people_count"),
    ("Start Date", "start_date"),
    ("Deadline", "deadline"),
    ("Project Objective", "project_objective"),
    ("Deliverable Output", "deliverable_output"),
    ("Completed By", "completed_by_text"),
)
_SUMMARY_HELPER_REQUIRED_FIELDS = (
    "project_name",
    "project_leader",
    "project_objective",
    "deliverable_output",
    "completed_by_text",
)
_TASKS_TABLE_HEADERS = ["Index", "Title", "Deadline", "Status", "Row Type", "Owners", "Timeline"]
_MEMBERS_TABLE_HEADERS = ["Slot", "Member ID", "Name"]
_TASK_SUB_OBJECTIVE_MARK = "\u2713"
_TIMELINE_SYMBOLS = {
    "planned": "\u25a1",
    "in_progress": "\u25cf",
    "completed": "\u25a0",
    "at_risk": "\u25b2",
    "blocked": "\u2715",
}
