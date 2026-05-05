from typing import Any
import logging
from .utils import (
    _col_index_to_letters, _range_to_grid_range, _hex_to_rgb,
    _border_style, _parse_range,
)
logger = logging.getLogger(__name__)
# ── Action dispatchers ──
def _exec_insert_rows(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    start = int(params["start_index"]) - 1  # convert to 0-based
    count = int(params.get("count", 1))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": start,
                            "endIndex": start + count,
                        },
                        "inheritFromBefore": True,
                    }
                }
            ]
        },
    ).execute()

def _exec_delete_rows(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    start = int(params["start_index"]) - 1  # 0-based
    count = int(params.get("count", 1))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": start,
                            "endIndex": start + count,
                        }
                    }
                }
            ]
        },
    ).execute()

def _exec_copy_format(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    from_range = str(params["from_range"])
    to_range = str(params["to_range"])
    fr1, fc1, fr2, fc2 = _parse_range(from_range)
    tr1, tc1, tr2, tc2 = _parse_range(to_range)
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "copyPaste": {
                        "source": {
                            "sheetId": sheet_id,
                            "startRowIndex": fr1 - 1,
                            "endRowIndex": fr2,
                            "startColumnIndex": fc1 - 1,
                            "endColumnIndex": fc2,
                        },
                        "destination": {
                            "sheetId": sheet_id,
                            "startRowIndex": tr1 - 1,
                            "endRowIndex": tr2,
                            "startColumnIndex": tc1 - 1,
                            "endColumnIndex": tc2,
                        },
                        "pasteType": "PASTE_FORMAT",
                        "pasteOrientation": "NORMAL",
                    }
                }
            ]
        },
    ).execute()

def _exec_set_value(service: Any, spreadsheet_id: str, params: dict, sheet_title: str) -> None:
    range_str = str(params["range"])
    value = params.get("value", "")
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!{range_str}",
        valueInputOption="USER_ENTERED",
        body={"values": [[value]]},
    ).execute()

def _exec_clear_content(service: Any, spreadsheet_id: str, params: dict, sheet_title: str) -> None:
    range_str = str(params["range"])
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!{range_str}",
        body={},
    ).execute()

def _exec_clear_sheet(service: Any, spreadsheet_id: str, params: dict, sheet_id: int, sheet_title: str = "OPPM") -> None:
    """Clear the entire sheet: values, formatting, merges, then reset dimensions."""
    # 1. Clear all values
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!A1:AL1000",
        body={},
    ).execute()

    # 2. Unmerge all cells
    merges = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[f"'{sheet_title}'"],
        fields="sheets.merges",
    ).execute()
    merge_requests = []
    for sheet in merges.get("sheets", []):
        for merge in sheet.get("merges", []):
            merge_requests.append({"unmergeCells": {"range": merge}})
    if merge_requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": merge_requests},
        ).execute()

    # 3. Clear all formatting (borders, backgrounds, fonts, alignment, number format, etc.)
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1000,
                            "startColumnIndex": 0,
                            "endColumnIndex": 40,
                        },
                        "fields": "userEnteredFormat",
                    }
                }
            ]
        },
    ).execute()

    # 4. Reset row heights to default (21px for all rows)
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": 0,
                            "endIndex": 1000,
                        },
                        "properties": {"pixelSize": 21},
                        "fields": "pixelSize",
                    }
                }
            ]
        },
    ).execute()

    # 5. Reset column widths to standard OPPM values
    col_widths = [
        (0, 6, 40),    # A-F: 40px
        (6, 7, 10),    # G: 10px
        (7, 8, 50),    # H: 50px
        (8, 9, 280),   # I: 280px
        (9, 35, 25),   # J-AI: 25px
        (35, 38, 80),  # AJ-AL: 80px
    ]
    requests = []
    for start, end, width in col_widths:
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": start,
                    "endIndex": end,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


