import types

import pytest
from fastapi import HTTPException

from domains.oppm.google_sheets.mapping import (
    _resolve_oppm_mapping_profile,
    _resolve_explicit_oppm_mapping,
    _resolve_helper_sheet_profile,
)
from domains.oppm.google_sheets.writer import (
    _push_to_google_sheet,
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

    monkeypatch.setattr("domains.oppm.google_sheets.layout._read_sheet_layout", lambda *_args, **_kwargs: layout)

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

    monkeypatch.setattr("domains.oppm.google_sheets.layout._read_sheet_layout", lambda *_args, **_kwargs: layout)

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

    monkeypatch.setattr("domains.oppm.google_sheets.layout._read_sheet_layout", lambda *_args, **_kwargs: layout)

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

    monkeypatch.setattr("domains.oppm.google_sheets.layout._read_sheet_layout", lambda *_args, **_kwargs: layout)

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


def test_resolve_mapping_profile_detects_task_regions_and_people_count(monkeypatch):
    layout = _build_layout(
        cells={
            (1, 1): "Project Leader: Jane Doe",
            (1, 21): "Project Name: Store Revamp",
            (3, 1): "Project Objective:",
            (4, 1): "Deliverable Output:",
            (5, 1): "Start Date:",
            (6, 1): "Deadline:",
            (7, 1): "Sub Objective",
            (7, 7): "Major Tasks (Deadline)",
            (7, 21): "Project Completed By: 2026-06-01",
            (7, 25): "Owner / Priority",
            (12, 1): "# People working on the project: 3",
        },
        merges=[
            {"startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 0, "endColumnIndex": 6},
            {"startRowIndex": 3, "endRowIndex": 4, "startColumnIndex": 0, "endColumnIndex": 6},
            {"startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 0, "endColumnIndex": 6},
            {"startRowIndex": 5, "endRowIndex": 6, "startColumnIndex": 0, "endColumnIndex": 6},
            {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 0, "endColumnIndex": 6},
            {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 6, "endColumnIndex": 20},
            {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 20, "endColumnIndex": 24},
            {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 24, "endColumnIndex": 30},
        ],
        max_row=80,
        max_col=40,
    )

    monkeypatch.setattr("domains.oppm.google_sheets.layout._read_sheet_layout", lambda *_args, **_kwargs: layout)

    profile = _resolve_oppm_mapping_profile(types.SimpleNamespace(), "sheet-layout")

    assert profile["source"] == "layout_detected"
    assert profile["task_anchor"]["column"] == "G"
    assert profile["task_anchor"]["first_row"] == 8
    assert profile["task_anchor"]["max_rows"] == 4
    assert profile["anchors"]["people_count"] == "A12"
    assert profile["regions"]["sub_objectives"]["start_col"] == 1
    assert profile["regions"]["sub_objectives"]["end_col"] == 6
    assert profile["regions"]["timeline"]["start_col"] == 21
    assert profile["regions"]["timeline"]["end_col"] == 24
    assert profile["regions"]["owners"]["start_col"] == 25
    assert profile["regions"]["owners"]["end_col"] == 30


def test_resolve_mapping_profile_detects_grouped_task_rows(monkeypatch):
    layout = _build_layout(
        cells={
            (1, 8): "Project Leader:",
            (1, 11): "Project Name:",
            (2, 8): "Project Objective:",
            (3, 8): "Deliverable Output:",
            (4, 8): "Start Date:",
            (5, 8): "Deadline:",
            (7, 2): "Sub objective",
            (7, 9): "Major Tasks (Deadline)",
            (7, 13): "Project Completed By:",
            (7, 17): "Owner / Priority",
            (24, 1): "# People working on the project: 3",
        },
        merges=[
            {"startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 7, "endColumnIndex": 10},
            {"startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 10, "endColumnIndex": 20},
            {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 1, "endColumnIndex": 7},
            {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 12, "endColumnIndex": 16},
            {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 16, "endColumnIndex": 22},
            {"startRowIndex": 7, "endRowIndex": 8, "startColumnIndex": 7, "endColumnIndex": 12},
            {"startRowIndex": 8, "endRowIndex": 9, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 9, "endRowIndex": 10, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 10, "endRowIndex": 11, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 11, "endRowIndex": 12, "startColumnIndex": 7, "endColumnIndex": 12},
            {"startRowIndex": 12, "endRowIndex": 13, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 13, "endRowIndex": 14, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 14, "endRowIndex": 15, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 15, "endRowIndex": 16, "startColumnIndex": 7, "endColumnIndex": 12},
            {"startRowIndex": 16, "endRowIndex": 17, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 17, "endRowIndex": 18, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 18, "endRowIndex": 19, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 19, "endRowIndex": 20, "startColumnIndex": 7, "endColumnIndex": 12},
            {"startRowIndex": 20, "endRowIndex": 21, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 21, "endRowIndex": 22, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 22, "endRowIndex": 23, "startColumnIndex": 8, "endColumnIndex": 12},
        ],
        max_row=40,
        max_col=30,
    )

    monkeypatch.setattr("domains.oppm.google_sheets.layout._read_sheet_layout", lambda *_args, **_kwargs: layout)

    profile = _resolve_oppm_mapping_profile(types.SimpleNamespace(), "sheet-grouped")

    assert profile["source"] == "layout_detected"
    assert profile["task_anchor"]["column"] == "H"
    assert profile["task_anchor"]["first_row"] == 8
    assert profile["task_rows"][:5] == [
        {"row": 8, "kind": "main", "write_col": 8},
        {"row": 9, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
        {"row": 10, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
        {"row": 11, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
        {"row": 12, "kind": "main", "write_col": 8},
    ]


def test_resolve_mapping_profile_detects_merged_summary_block(monkeypatch):
    layout = _build_layout(
        cells={
            (2, 8): "Project Leader: Project Manager",
            (2, 11): "Project Name: 3d Enhancement Project",
            (3, 8): "Project Objective: Text\nDeliverable Output : Text\nStart Date:\nDeadline:",
            (5, 2): "Sub objective",
            (5, 9): "Major Tasks (Deadline)",
            (5, 13): "Project Completed By: 8 weeks",
            (5, 30): "Owner / Priority",
            (29, 12): "# People working on the project",
        },
        merges=[
            {"startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 7, "endColumnIndex": 10},
            {"startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 10, "endColumnIndex": 35},
            {"startRowIndex": 2, "endRowIndex": 4, "startColumnIndex": 7, "endColumnIndex": 35},
            {"startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 1, "endColumnIndex": 7},
            {"startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 12, "endColumnIndex": 29},
            {"startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 29, "endColumnIndex": 35},
            {"startRowIndex": 5, "endRowIndex": 6, "startColumnIndex": 7, "endColumnIndex": 12},
            {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 7, "endRowIndex": 8, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 9, "endRowIndex": 10, "startColumnIndex": 7, "endColumnIndex": 12},
            {"startRowIndex": 10, "endRowIndex": 11, "startColumnIndex": 8, "endColumnIndex": 12},
        ],
        max_row=40,
        max_col=40,
    )

    monkeypatch.setattr("domains.oppm.google_sheets.layout._read_sheet_layout", lambda *_args, **_kwargs: layout)

    profile = _resolve_oppm_mapping_profile(types.SimpleNamespace(), "sheet-merged-summary")

    assert profile["source"] == "layout_detected"
    assert profile["summary_block_anchor"] == "H3"
    assert profile["summary_block_range"] == "H3:AI4"
    assert profile["anchors"]["project_leader"] == "H2"
    assert profile["anchors"]["project_name"] == "K2"
    assert profile["anchors"]["completed_by"] == "M5"
    assert "project_objective" not in profile["anchors"]
    assert "deliverable_output" not in profile["anchors"]
    assert "start_date" not in profile["anchors"]
    assert "deadline" not in profile["anchors"]
    assert profile["regions"]["timeline"]["start_col"] == 13
    assert profile["regions"]["timeline"]["end_col"] == 29
    assert profile["regions"]["owners"]["start_col"] == 30
    assert profile["regions"]["owners"]["end_col"] == 35
    assert profile["missing_anchors"] == []
    assert set(profile["clear_anchors"]) >= {"A1", "U1", "U7", "G3", "G4", "G5", "G6"}


def test_write_oppm_sheet_values_writes_grouped_task_rows() -> None:
    service = _FakeService()
    tasks = [
        types.SimpleNamespace(index="1", title="Sales Order Modification", deadline=None, status=None, is_sub=False, sub_objective_positions=[], owners=[], timeline=[]),
        types.SimpleNamespace(index="2", title="Stock Management Enhancement", deadline=None, status=None, is_sub=False, sub_objective_positions=[], owners=[], timeline=[]),
        types.SimpleNamespace(index="2.1", title="Update beginning stock", deadline="2026-04-26", status="completed", is_sub=True, sub_objective_positions=[], owners=[], timeline=[]),
        types.SimpleNamespace(index="2.2", title="Stock alert configuration", deadline="2026-05-03", status="todo", is_sub=True, sub_objective_positions=[], owners=[], timeline=[]),
        types.SimpleNamespace(index="2.3", title="Build stock alert", deadline="2026-05-03", status="todo", is_sub=True, sub_objective_positions=[], owners=[], timeline=[]),
        types.SimpleNamespace(index="3", title="Mobile App New Features", deadline=None, status=None, is_sub=False, sub_objective_positions=[], owners=[], timeline=[]),
        types.SimpleNamespace(index="4", title="Purchase Order & Route Optimization", deadline=None, status=None, is_sub=False, sub_objective_positions=[], owners=[], timeline=[]),
        types.SimpleNamespace(index="4.1", title="Key in PO in the system", deadline="2026-05-10", status="todo", is_sub=True, sub_objective_positions=[], owners=[], timeline=[]),
        types.SimpleNamespace(index="4.2", title="Route planning", deadline="2026-05-17", status="todo", is_sub=True, sub_objective_positions=[], owners=[], timeline=[]),
        types.SimpleNamespace(index="4.3", title="Route planning module", deadline="2026-05-17", status="todo", is_sub=True, sub_objective_positions=[], owners=[], timeline=[]),
    ]

    rows_written, diagnostics = _write_oppm_sheet_values(
        service,
        "sheet-grouped-write",
        {},
        tasks,
        [],
        {
            "source": "layout_detected",
            "anchors": {},
            "task_anchor": {"column": "H", "first_row": 8, "max_rows": 16},
            "task_rows": [
                {"row": 8, "kind": "main", "write_col": 8},
                {"row": 9, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 10, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 11, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 12, "kind": "main", "write_col": 8},
                {"row": 13, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 14, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 15, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 16, "kind": "main", "write_col": 8},
                {"row": 17, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 18, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 19, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 20, "kind": "main", "write_col": 8},
                {"row": 21, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 22, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
                {"row": 23, "kind": "sub", "index_col": 8, "title_col": 9, "write_col": 9},
            ],
            "regions": {},
            "clear_anchors": [],
        },
    )

    assert rows_written == 10
    assert diagnostics["writes"]["skipped"] == 0
    assert len(service.values_api.batch_updates) == 1

    written_values = {
        item["range"]: item["values"]
        for item in service.values_api.batch_updates[0]["body"]["data"]
    }
    assert written_values["'OPPM'!H8"] == [["1  Sales Order Modification"]]
    assert written_values["'OPPM'!H9"] == [["2"]]
    assert written_values["'OPPM'!I9"] == [["Stock Management Enhancement"]]
    assert written_values["'OPPM'!H10"] == [["2.1"]]
    assert written_values["'OPPM'!I10"] == [["Update beginning stock"]]
    assert written_values["'OPPM'!H11"] == [["2.2"]]
    assert written_values["'OPPM'!I11"] == [["Stock alert configuration"]]
    assert written_values["'OPPM'!H12"] == [["2.3  Build stock alert"]]
    assert written_values["'OPPM'!H13"] == [["3"]]
    assert written_values["'OPPM'!I13"] == [["Mobile App New Features"]]
    assert written_values["'OPPM'!H14"] == [["4"]]
    assert written_values["'OPPM'!I14"] == [["Purchase Order & Route Optimization"]]
    assert written_values["'OPPM'!H15"] == [["4.1"]]
    assert written_values["'OPPM'!I15"] == [["Key in PO in the system"]]
    assert written_values["'OPPM'!H16"] == [["4.2  Route planning"]]
    assert written_values["'OPPM'!H17"] == [["4.3"]]
    assert written_values["'OPPM'!I17"] == [["Route planning module"]]


def test_write_oppm_sheet_values_writes_summary_block_and_timeline_header() -> None:
    service = _FakeService()
    fills = {
        "project_leader": "Project Manager",
        "project_name": "3d Enhancement Project",
        "project_objective": "Enhance the existing system",
        "deliverable_output": "Enhanced system modules",
        "start_date": "2026-02-09",
        "deadline": "2026-05-01",
        "completed_by_text": "8 weeks",
    }

    rows_written, diagnostics = _write_oppm_sheet_values(
        service,
        "sheet-summary-block-write",
        fills,
        [],
        [],
        {
            "source": "layout_detected",
            "anchors": {
                "project_leader": "H2",
                "project_name": "K2",
                "completed_by": "M5",
            },
            "summary_block_anchor": "H3",
            "summary_block_range": "H3:AI4",
            "task_anchor": {"column": "H", "first_row": 6, "max_rows": 16},
            "task_rows": [],
            "regions": {
                "timeline": {"start_col": 13, "end_col": 29, "first_row": 6, "max_rows": 16},
            },
            "clear_anchors": ["A1", "U1", "U7", "G3", "G4", "G5", "G6"],
        },
    )

    assert rows_written == 0
    assert diagnostics["writes"]["attempted"] == 4
    assert len(service.values_api.batch_updates) == 1

    written_values = {
        item["range"]: item["values"]
        for item in service.values_api.batch_updates[0]["body"]["data"]
    }
    assert written_values["'OPPM'!H2"] == [["Project Leader: Project Manager"]]
    assert written_values["'OPPM'!K2"] == [["Project Name: 3d Enhancement Project"]]
    assert written_values["'OPPM'!M5"] == [["Project Completed By: 8 weeks | 2026-02-09 -> 2026-05-01"]]
    assert written_values["'OPPM'!H3:AI4"] == [[
        "Project Objective: Enhance the existing system\n"
        "Deliverable Output: Enhanced system modules\n"
        "Start Date: 2026-02-09\n"
        "Deadline: 2026-05-01"
    ]]

    clear_ranges = {item["range"] for item in service.values_api.clears}
    assert "'OPPM'!A1" in clear_ranges
    assert "'OPPM'!G3" in clear_ranges
    assert "'OPPM'!U7" in clear_ranges


def test_partial_layout_fallback_prefers_detected_leader_anchor_over_stale_a1(monkeypatch):
    layout = _build_layout(
        cells={
            (1, 1): "Project Leader: Project Manager",
            (2, 9): "Project Leader:",
            (3, 9): "Project Objective: Text",
            (4, 9): "Deliverable Output:",
            (5, 9): "Start Date:",
            (6, 9): "Deadline:",
            (7, 7): "Major Tasks (Deadline)",
            (7, 21): "Project Completed By:",
        },
        merges=[
            {"startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 8, "endColumnIndex": 19},
            {"startRowIndex": 3, "endRowIndex": 4, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 5, "endRowIndex": 6, "startColumnIndex": 8, "endColumnIndex": 12},
            {"startRowIndex": 6, "endRowIndex": 7, "startColumnIndex": 20, "endColumnIndex": 24},
        ],
        max_row=80,
        max_col=40,
    )

    monkeypatch.setattr("domains.oppm.google_sheets.layout._read_sheet_layout", lambda *_args, **_kwargs: layout)

    profile = _resolve_oppm_mapping_profile(types.SimpleNamespace(), "sheet-partial")

    assert profile["source"] == "classic_fallback"
    assert profile["anchors"]["project_leader"] == "I2"
    assert "A1" in profile["clear_anchors"]
    assert "project_name" not in profile["anchors"]
    assert "project_objective" not in profile["anchors"]
    assert profile["task_anchor"]["column"] == "G"
    assert profile["task_anchor"]["first_row"] == 8


def test_write_oppm_sheet_values_clears_stale_fallback_anchor() -> None:
    service = _FakeService()

    _write_oppm_sheet_values(
        service,
        "sheet-stale",
        {"project_leader": "Project Manager"},
        [],
        [],
        {
            "source": "classic_fallback",
            "anchors": {"project_leader": "I2"},
            "task_anchor": {"column": "G", "first_row": 8, "max_rows": 4},
            "regions": {},
            "clear_anchors": ["A1"],
        },
    )

    assert service.values_api.clears[0]["range"] == "'OPPM'!A1"


def test_write_oppm_sheet_values_writes_task_regions() -> None:
    service = _FakeService()
    fills = {
        "project_name": "Store Revamp",
        "project_objective": "Modernize the storefront",
        "start_date": "2026-05-04",
        "deadline": "2026-05-25",
        "people_count": "2",
    }
    tasks = [
        types.SimpleNamespace(
            index="1.1",
            title="Discovery",
            deadline="2026-05-05",
            status="in_progress",
            is_sub=True,
            sub_objective_positions=[1, 3],
            owners=[types.SimpleNamespace(member_id="m-1", priority="A")],
            timeline=[types.SimpleNamespace(week_start="2026-05-04", status="in_progress")],
        ),
        types.SimpleNamespace(
            index="1.2",
            title="Build",
            deadline="2026-05-19",
            status="completed",
            is_sub=True,
            sub_objective_positions=[2],
            owners=[types.SimpleNamespace(member_id="m-2", priority="B")],
            timeline=[types.SimpleNamespace(week_start="2026-05-18", status="completed")],
        ),
    ]
    members = [
        types.SimpleNamespace(id="m-1", slot=0, name="Alice"),
        types.SimpleNamespace(id="m-2", slot=1, name="Bob"),
    ]

    rows_written, diagnostics = _write_oppm_sheet_values(
        service,
        "sheet-6",
        fills,
        tasks,
        members,
        {
            "source": "layout_detected",
            "anchors": {
                "project_objective": "G3",
                "people_count": "A12",
            },
            "task_anchor": {
                "column": "G",
                "first_row": 8,
                "max_rows": 4,
            },
            "regions": {
                "sub_objectives": {"start_col": 1, "end_col": 3, "first_row": 8, "max_rows": 4},
                "task_text": {"start_col": 7, "end_col": 20, "first_row": 8, "max_rows": 4},
                "timeline": {"start_col": 21, "end_col": 24, "first_row": 8, "max_rows": 4},
                "owners": {"start_col": 25, "end_col": 26, "first_row": 8, "max_rows": 4},
            },
        },
    )

    assert rows_written == 2
    assert diagnostics["writes"]["skipped"] == 0
    assert len(service.values_api.batch_updates) == 1

    anchor_ranges = [item["range"] for item in service.values_api.batch_updates[0]["body"]["data"]]
    assert "'OPPM'!G3" in anchor_ranges
    assert "'OPPM'!A12" in anchor_ranges

    updates_by_range = {item["range"]: item["body"]["values"] for item in service.values_api.updates}
    assert updates_by_range["'OPPM'!A8:C9"] == [["✓", "", "✓"], ["", "✓", ""]]
    assert updates_by_range["'OPPM'!G8:G9"] == [
        ["      1.1  Discovery  (2026-05-05)"],
        ["      1.2  Build  (2026-05-19)"],
    ]
    assert updates_by_range["'OPPM'!U8:X9"] == [["●", "", "", ""], ["", "", "■", ""]]
    assert updates_by_range["'OPPM'!Y8:Z9"] == [["A", ""], ["", "B"]]


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
        "domains.oppm.google_sheets.layout._read_sheet_layout",
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

    monkeypatch.setattr("domains.oppm.google_sheets.credentials._build_sheets_service", lambda *_args, **_kwargs: service)
    monkeypatch.setattr("domains.oppm.google_sheets.writer._ensure_sheet_tabs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("domains.oppm.google_sheets.mapping._resolve_helper_sheet_profile", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "domains.oppm.google_sheets.mapping._resolve_oppm_mapping_profile",
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

def test_push_to_google_sheet_writes_oppm_alongside_helper_sheets(monkeypatch) -> None:
    service = _FakeService()
    task_sheet_calls: list[str] = []

    monkeypatch.setattr("domains.oppm.google_sheets.credentials._build_sheets_service", lambda *_args, **_kwargs: service)
    monkeypatch.setattr("domains.oppm.google_sheets.writer._ensure_sheet_tabs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "domains.oppm.google_sheets.mapping._resolve_helper_sheet_profile",
        lambda *_args, **_kwargs: {
            "source": "helper_sheet_profile",
            "summary_anchors": {"project_name": "B2"},
            "resolved_fields": {"project_name": {"source": "helper_sheet", "target": "OPPM Summary!B2"}},
        },
    )
    monkeypatch.setattr(
        "domains.oppm.google_sheets.writer._write_summary_helper_sheet_values",
        lambda *_args, **_kwargs: (
            9,
            {
                "mapping": {"source": "helper_sheet_profile"},
                "writes": {"attempted": 1, "applied": 1, "skipped": 0},
            },
        ),
    )

    oppm_mapping = {
        "source": "classic_fallback",
        "task_anchor": {"column": "H", "first_row": 6, "max_rows": 16},
        "regions": {},
        "task_rows": [{"row": 6, "kind": "main", "write_col": 8}],
        "anchors": {},
        "clear_anchors": [],
        "missing_anchors": [],
    }
    monkeypatch.setattr("domains.oppm.google_sheets.mapping._resolve_oppm_mapping_profile", lambda *_args, **_kwargs: oppm_mapping)
    monkeypatch.setattr(
        "domains.oppm.google_sheets.writer._write_oppm_sheet_values",
        lambda *_args, **_kwargs: (
            10,
            {
                "mapping": oppm_mapping,
                "writes": {"attempted": 4, "applied": 4, "skipped": 0},
            },
        ),
    )

    def _capture_sheet_write(_service, _spreadsheet_id, sheet_title, _headers, _rows):
        task_sheet_calls.append(sheet_title)

    monkeypatch.setattr("domains.oppm.google_sheets.writer._write_sheet_with_existing_headers", _capture_sheet_write)

    result = _push_to_google_sheet(
        {"client_email": "oppm-editor@example.com"},
        "sheet-helper-oppm",
        {"project_name": "Store Revamp"},
        [types.SimpleNamespace(index="1", title="Task", deadline=None, status=None, is_sub=False, owners=[], timeline=[])],
        [types.SimpleNamespace(id="m-1", slot=0, name="Alice")],
        None,
    )

    assert result["updated_sheets"] == ["OPPM", "OPPM Summary", "OPPM Tasks", "OPPM Members"]
    assert result["rows_written"]["oppm"] == 10
    assert result["rows_written"]["summary"] == 9
    assert result["diagnostics"]["mapping"]["source"] == "classic_fallback"
    assert task_sheet_calls == ["OPPM Tasks", "OPPM Members"]
