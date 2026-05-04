from typing import Any
import logging
from .utils import (
    _range_to_grid_range, _hex_to_rgb, _border_style,
)
logger = logging.getLogger(__name__)
def _exec_set_border(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    style = str(params.get("style", "SOLID"))
    color = str(params.get("color", "#CCCCCC"))
    width = int(params.get("width", 1))

    # Build per-side border objects; None means remove that side
    top = _border_style(str(params.get("top_style", style)), str(params.get("top_color", color)), int(params.get("top_width", width)))
    bottom = _border_style(str(params.get("bottom_style", style)), str(params.get("bottom_color", color)), int(params.get("bottom_width", width)))
    left = _border_style(str(params.get("left_style", style)), str(params.get("left_color", color)), int(params.get("left_width", width)))
    right = _border_style(str(params.get("right_style", style)), str(params.get("right_color", color)), int(params.get("right_width", width)))
    inner_h = _border_style(str(params.get("inner_horizontal_style", style)), str(params.get("inner_horizontal_color", color)), int(params.get("inner_horizontal_width", width)))
    inner_v = _border_style(str(params.get("inner_vertical_style", style)), str(params.get("inner_vertical_color", color)), int(params.get("inner_vertical_width", width)))

    request: dict = {
        "updateBorders": {
            "range": _range_to_grid_range(range_str, sheet_id),
        }
    }
    if top is not None:
        request["updateBorders"]["top"] = top
    if bottom is not None:
        request["updateBorders"]["bottom"] = bottom
    if left is not None:
        request["updateBorders"]["left"] = left
    if right is not None:
        request["updateBorders"]["right"] = right
    if inner_h is not None:
        request["updateBorders"]["innerHorizontal"] = inner_h
    if inner_v is not None:
        request["updateBorders"]["innerVertical"] = inner_v

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [request]},
    ).execute()

def _exec_set_background(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    color_hex = str(params.get("color", "#FFFFFF"))
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": _hex_to_rgb(color_hex)
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                }
            ]
        },
    ).execute()

def _exec_clear_background(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                }
            ]
        },
    ).execute()

def _exec_set_text_wrap(service: Any, spreadsheet_id: str, params: dict, sheet_id: int) -> None:
    range_str = str(params["range"])
    mode = str(params.get("mode", "CLIP")).upper()
    if mode not in ("CLIP", "WRAP", "OVERFLOW_CELL"):
        mode = "CLIP"
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": _range_to_grid_range(range_str, sheet_id),
                        "cell": {
                            "userEnteredFormat": {"wrapStrategy": mode}
                        },
                        "fields": "userEnteredFormat.wrapStrategy",
                    }
                }
            ]
        },
    ).execute()

