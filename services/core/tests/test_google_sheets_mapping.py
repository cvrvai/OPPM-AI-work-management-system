import types

import pytest
from fastapi import HTTPException

from services.google_sheets_service import (
    _push_to_google_sheet,
    _resolve_explicit_oppm_mapping,
    _resolve_helper_sheet_profile,
    _write_oppm_sheet_values,
    _write_summary_helper_sheet_values,
)


def _build_layout(
    cells: dict[tuple[int, int], str],
    merges: list[dict[str, int]] | None = None,
    max_row: int = 120,
    max_col: int = 52,
) -> dict:
    max_used_row = max((row for row, _ in cells), default=1)
    row_data = []
    for row in range(1, max_used_row + 1):
        row_cells = {col: value for (r, col), value in cells.items() if r == row}
        if not row_cells:
            row_data.append({})
            continue

        max_used_col = max(row_cells)
        values = [{} for _ in range(max_used_col)]
        for col, value in row_cells.items():
            values[col - 1] = {"formattedValue": value}
        row_data.append({"values": values})

    return {
        "row_data": row_data,
        "merges": merges or [],
        "max_row": max_row,
        "max_col": max_col,
    }


class _FakeValuesApi:
    def __init__(self) -> None:
        self.batch_updates: list[dict] = []
        self.clears: list[dict] = []
        self.updates: list[dict] = []

    def batchUpdate(self, spreadsheetId: str, body: dict):
        self.batch_updates.append({"spreadsheetId": spreadsheetId, "body": body})
        return types.SimpleNamespace(execute=lambda: {})

    def update(self, spreadsheetId: str, range: str, valueInputOption: str, body: dict):
        self.updates.append({
            "spreadsheetId": spreadsheetId,
            "range": range,
            "valueInputOption": valueInputOption,
            "body": body,
        })
        return types.SimpleNamespace(execute=lambda: {})

    def clear(self, spreadsheetId: str, range: str, body: dict):
        self.clears.append({"spreadsheetId": spreadsheetId, "range": range, "body": body})
        return types.SimpleNamespace(execute=lambda: {})


class _FakeSpreadsheetsApi:
    def __init__(self, values_api: _FakeValuesApi) -> None:
        self._values_api = values_api

    def values(self) -> _FakeValuesApi:
        return self._values_api


class _FakeService:
    def __init__(self) -> None:
        self.values_api = _FakeValuesApi()

    def spreadsheets(self) -> _FakeSpreadsheetsApi:
        return _FakeSpreadsheetsApi(self.values_api)


def test_resolve_explicit_row_column_mapping(monkeypatch):
    layout = _build_layout(
        cells={},
    )

    monkeypatch.setattr("services.google_sheets_service._read_sheet_layout", lambda *_args, **_kwargs: layout)

    profile = _resolve_explicit_oppm_mapping(
        types.SimpleNamespace(),
        "sheet-1",
        {
            "project_leader": {"row": 1, "column": 1},
            "project_name": {"row": 1, "column": 21},
            "task_anchor": {"row": 8, "column": 7},
        },
    )

    assert profile["source"] == "explicit_mapping"
    assert profile["anchors"]["project_leader"] == "A1"
    assert profile["anchors"]["project_name"] == "U1"
    assert profile["task_anchor"]["column"] == "G"
    assert profile["task_anchor"]["first_row"] == 8
    assert profile["task_anchor"]["max_rows"] == 64


def test_resolve_explicit_label_mapping_for_inline_and_value_targets(monkeypatch):
    layout = _build_layout(
        cells={
            (2, 3): "Project Leader: Shifted",
            (5, 3): "Project Objective:",
            (6, 3): "Deliverable Output:",
            (10, 10): "Major Tasks (Deadline)",
        },
        merges=[
            {"startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 2, "endColumnIndex": 8},
            {"startRowIndex": 5, "endRowIndex": 6, "startColumnIndex": 2, "endColumnIndex": 8},
        ],
        max_row=160,
        max_col=60,
    )

    monkeypatch.setattr("services.google_sheets_service._read_sheet_layout", lambda *_args, **_kwargs: layout)

    profile = _resolve_explicit_oppm_mapping(
        types.SimpleNamespace(),
        "sheet-2",
        {
            "project_leader": {"label": "Project Leader"},
            "project_objective": {"label": "Project Objective"},
            "deliverable_output": {"label": "Deliverable Output"},
            "task_anchor": {"label": "Major Tasks (Deadline)"},
        },
    )

    assert profile["source"] == "explicit_mapping"
    assert profile["anchors"]["project_leader"] == "C2"
    assert profile["anchors"]["project_objective"] == "I5"
    assert profile["anchors"]["deliverable_output"] == "I6"
    assert profile["task_anchor"]["column"] == "J"
    assert profile["task_anchor"]["first_row"] == 11


def test_resolve_explicit_mapping_rejects_unknown_fields(monkeypatch):
    layout = _build_layout(
        cells={},
    )

    monkeypatch.setattr("services.google_sheets_service._read_sheet_layout", lambda *_args, **_kwargs: layout)

    with pytest.raises(HTTPException) as error:
        _resolve_explicit_oppm_mapping(
            types.SimpleNamespace(),
            "sheet-3",
            {"unknown_field": {"row": 1, "column": 1}},
        )

    assert error.value.status_code == 400
    assert "unknown_field" in error.value.detail
    assert "unsupported field id" in error.value.detail


def test_resolve_explicit_mapping_rejects_ambiguous_and_missing_labels(monkeypatch):
    layout = _build_layout(
        cells={
            (3, 1): "Project Objective:",
            (8, 1): "Project Objective:",
        },
        merges=[
            {"startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 0, "endColumnIndex": 6},
            {"startRowIndex": 3, "endRowIndex": 4, "startColumnIndex": 0, "endColumnIndex": 6},
            {"startRowIndex": 7, "endRowIndex": 8, "startColumnIndex": 0, "endColumnIndex": 6},
        ],
    )

    monkeypatch.setattr("services.google_sheets_service._read_sheet_layout", lambda *_args, **_kwargs: layout)

    with pytest.raises(HTTPException) as error:
        _resolve_explicit_oppm_mapping(
            types.SimpleNamespace(),
            "sheet-4",
            {
                "project_objective": {"label": "Project Objective"},
                "completed_by": {"label": "Project Completed By"},
            },
        )

    assert error.value.status_code == 400
    assert "project_objective" in error.value.detail
    assert 'label "Project Objective" matched 2 cells' in error.value.detail
    assert "completed_by" in error.value.detail
    assert 'label "Project Completed By" was not found' in error.value.detail


def test_write_oppm_sheet_values_omits_unmapped_fields() -> None:
    service = _FakeService()
    fills = {
        "project_leader": "Jane Doe",
        "project_name": "Store Revamp",
        "project_objective": "Modernize the storefront",
        "deliverable_output": "Updated customer workflow",
        "start_date": "2026-05-01",
        "deadline": "2026-06-15",
        "completed_by_text": "Operations team",
    }

    rows_written, diagnostics = _write_oppm_sheet_values(
        service,
        "sheet-5",
        fills,
        [],
        {
            "source": "explicit_mapping",
            "anchors": {
                "project_objective": "G3",
                "deliverable_output": "G4",
            },
            "task_anchor": None,
        },
    )

    assert rows_written == 0
    assert diagnostics["mapping"]["source"] == "explicit_mapping"
    assert len(service.values_api.batch_updates) == 1

    written_ranges = [
        item["range"]
        for item in service.values_api.batch_updates[0]["body"]["data"]
    ]
    assert written_ranges == ["'OPPM'!G3", "'OPPM'!G4"]
    assert "'OPPM'!A1" not in written_ranges
    assert "'OPPM'!U1" not in written_ranges


def test_resolve_helper_sheet_profile_uses_summary_labels(monkeypatch):
    summary_layout = _build_layout(
        cells={
            (2, 1): "Project Name",
            (3, 1): "Project Leader",
            (5, 1): "Start Date",
            (6, 1): "Deadline",
            (7, 1): "Project Objective",
            (8, 1): "Deliverable Output",
            (9, 1): "Completed By",
        },
    )

    monkeypatch.setattr(
        "services.google_sheets_service._read_sheet_layout",
        lambda _service, _spreadsheet_id, _sheet_title: summary_layout,
    )

    profile = _resolve_helper_sheet_profile(types.SimpleNamespace(), "sheet-helper")

    assert profile is not None
    assert profile["source"] == "helper_sheet_profile"
    assert profile["summary_anchors"]["project_name"] == "B2"
    assert profile["summary_anchors"]["project_leader"] == "B3"
    assert profile["summary_anchors"]["project_objective"] == "B7"
    assert profile["resolved_fields"]["task_anchor"]["target"] == "OPPM Tasks!A2"


def test_write_summary_helper_sheet_values_targets_helper_cells() -> None:
    service = _FakeService()
    fills = {
        "project_name": "3d Enhancement Project",
        "project_leader": "Project Manager",
        "start_date": "2026-02-09",
        "deadline": "2026-05-01",
        "project_objective": "Enhance the existing system",
        "deliverable_output": "Enhanced system modules",
        "completed_by_text": "8 weeks",
    }

    rows_written, diagnostics = _write_summary_helper_sheet_values(
        service,
        "sheet-summary",
        fills,
        {
            "source": "helper_sheet_profile",
            "summary_anchors": {
                "project_name": "B2",
                "project_leader": "B3",
                "start_date": "B5",
                "deadline": "B6",
                "project_objective": "B7",
                "deliverable_output": "B8",
                "completed_by_text": "B9",
            },
            "resolved_fields": {
                "project_name": {"source": "helper_sheet", "target": "OPPM Summary!B2"},
            },
        },
    )

    assert rows_written == 7
    assert diagnostics["mapping"]["source"] == "helper_sheet_profile"
    assert len(service.values_api.batch_updates) == 1

    written_ranges = [
        item["range"]
        for item in service.values_api.batch_updates[0]["body"]["data"]
    ]
    assert "'OPPM Summary'!B2" in written_ranges
    assert "'OPPM Summary'!B7" in written_ranges
    assert "'OPPM Summary'!B9" in written_ranges


def test_push_to_google_sheet_rejects_unresolved_mapping(monkeypatch) -> None:
    service = _FakeService()

    monkeypatch.setattr("services.google_sheets_service._build_sheets_service", lambda *_args, **_kwargs: service)
    monkeypatch.setattr("services.google_sheets_service._ensure_sheet_tabs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("services.google_sheets_service._resolve_helper_sheet_profile", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "services.google_sheets_service._resolve_oppm_mapping_profile",
        lambda *_args, **_kwargs: {
            "source": "unresolved",
            "confidence": 0.125,
            "fallback_used": False,
            "anchors": {},
            "task_anchor": {"column": None, "first_row": 0, "max_rows": 0},
            "missing_anchors": ["project_objective", "task_header"],
        },
    )

    with pytest.raises(HTTPException) as error:
        _push_to_google_sheet(
            {"client_email": "oppm-editor@example.com"},
            "sheet-unresolved",
            {"project_name": "Test Project"},
            [],
            [],
            None,
        )

    assert error.value.status_code == 422
    assert "layout was not recognized" in error.value.detail
    assert "project_objective" in error.value.detail
    assert service.values_api.batch_updates == []
    assert service.values_api.updates == []
    assert service.values_api.clears == []
