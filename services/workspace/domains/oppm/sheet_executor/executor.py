from typing import Any
import logging
from .utils import _find_sheet_id
from .data_builders import (
    _exec_insert_rows, _exec_delete_rows, _exec_copy_format,
    _exec_set_value, _exec_clear_content, _exec_clear_sheet,
)
from .format_builders import (
    _exec_set_border, _exec_set_background, _exec_clear_background, _exec_set_text_wrap,
)
from .scaffold import (
    _exec_scaffold_oppm_form, _exec_fill_timeline, _exec_clear_timeline,
    _exec_set_owner, _exec_set_bold, _exec_set_text_color, _exec_set_note,
    _exec_merge_cells, _exec_unmerge_cells, _exec_set_formula, _exec_set_number_format,
    _exec_set_alignment, _exec_set_font_size, _exec_insert_image, _exec_upload_asset_to_drive,
    _exec_set_text_rotation, _exec_set_font_family, _exec_set_row_height, _exec_set_column_width,
    _exec_freeze_rows, _exec_freeze_columns, _exec_set_conditional_formatting,
    _exec_set_data_validation, _exec_set_hyperlink, _exec_protect_range, _exec_unprotect_range,
)
logger = logging.getLogger(__name__)
# ── Public dispatcher ──

_SHEET_NAME_FROM_PARAMS = "OPPM"

SUPPORTED_ACTIONS = frozenset({
    "insert_rows", "delete_rows", "copy_format", "set_border",
    "set_background", "clear_background", "set_text_wrap",
    "set_value", "clear_content", "fill_timeline", "clear_timeline", "set_owner",
    "set_bold", "set_text_color", "set_note",
    "merge_cells", "unmerge_cells",
    "set_formula", "set_number_format", "set_alignment",
    "set_font_size", "set_font_family", "set_text_rotation", "insert_image", "upload_asset_to_drive",
    "set_row_height", "set_column_width",
    "freeze_rows", "freeze_columns",
    "set_conditional_formatting", "set_data_validation",
    "set_hyperlink",
    "protect_range", "unprotect_range",
    "clear_sheet",
    "scaffold_oppm_form",
})


def execute_actions(
    service: Any,
    spreadsheet_id: str,
    actions: list[dict],
    *,
    sa_info: dict[str, Any] | None = None,
) -> list[dict]:
    """Execute a list of OPPM AI sheet actions synchronously.

    Returns a list of result dicts: {action, success, error}.
    Each action is executed independently; failures do not abort the sequence.

    sa_info is the service account credential dict — passed through to actions
    that need to build a Drive client on demand (e.g. upload_asset_to_drive,
    scaffold_oppm_form when matrix_image_asset is supplied).
    """
    sheet_title = _SHEET_NAME_FROM_PARAMS
    try:
        sheet_id = _find_sheet_id(service, spreadsheet_id, sheet_title)
    except Exception as e:
        logger.warning("execute_actions: cannot find sheet '%s': %s", sheet_title, e)
        return [
            {"action": a.get("action", "unknown"), "success": False, "error": str(e)}
            for a in actions
        ]

    results: list[dict] = []
    for action_obj in actions:
        action_name = str(action_obj.get("action", ""))
        # Support both nested params {action, params: {...}} and flat {action, range, value}
        if "params" in action_obj:
            params = dict(action_obj.get("params", {}))
        else:
            params = {k: v for k, v in action_obj.items() if k != "action"}

        if action_name not in SUPPORTED_ACTIONS:
            results.append({"action": action_name, "success": False, "error": f"Unsupported action: {action_name}"})
            continue

        # Inject sheet name from params if provided (AI may pass "sheet": "OPPM")
        if "sheet" in params:
            sheet_title = str(params.pop("sheet", sheet_title)) or sheet_title

        try:
            if action_name == "insert_rows":
                _exec_insert_rows(service, spreadsheet_id, params, sheet_id)
            elif action_name == "delete_rows":
                _exec_delete_rows(service, spreadsheet_id, params, sheet_id)
            elif action_name == "copy_format":
                _exec_copy_format(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_border":
                _exec_set_border(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_background":
                _exec_set_background(service, spreadsheet_id, params, sheet_id)
            elif action_name == "clear_background":
                _exec_clear_background(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_text_wrap":
                _exec_set_text_wrap(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_value":
                _exec_set_value(service, spreadsheet_id, params, sheet_title)
            elif action_name == "clear_content":
                _exec_clear_content(service, spreadsheet_id, params, sheet_title)
            elif action_name == "fill_timeline":
                _exec_fill_timeline(service, spreadsheet_id, params, sheet_id, sheet_title)
            elif action_name == "clear_timeline":
                _exec_clear_timeline(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_owner":
                _exec_set_owner(service, spreadsheet_id, params, sheet_title)
            elif action_name == "set_bold":
                _exec_set_bold(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_text_color":
                _exec_set_text_color(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_note":
                _exec_set_note(service, spreadsheet_id, params, sheet_id)
            elif action_name == "merge_cells":
                _exec_merge_cells(service, spreadsheet_id, params, sheet_id)
            elif action_name == "unmerge_cells":
                _exec_unmerge_cells(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_formula":
                _exec_set_formula(service, spreadsheet_id, params, sheet_title)
            elif action_name == "set_number_format":
                _exec_set_number_format(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_alignment":
                _exec_set_alignment(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_font_size":
                _exec_set_font_size(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_font_family":
                _exec_set_font_family(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_text_rotation":
                _exec_set_text_rotation(service, spreadsheet_id, params, sheet_id)
            elif action_name == "insert_image":
                _exec_insert_image(service, spreadsheet_id, params, sheet_title)
            elif action_name == "set_row_height":
                _exec_set_row_height(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_column_width":
                _exec_set_column_width(service, spreadsheet_id, params, sheet_id)
            elif action_name == "freeze_rows":
                _exec_freeze_rows(service, spreadsheet_id, params, sheet_id)
            elif action_name == "freeze_columns":
                _exec_freeze_columns(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_conditional_formatting":
                _exec_set_conditional_formatting(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_data_validation":
                _exec_set_data_validation(service, spreadsheet_id, params, sheet_id)
            elif action_name == "set_hyperlink":
                _exec_set_hyperlink(service, spreadsheet_id, params, sheet_title)
            elif action_name == "protect_range":
                _exec_protect_range(service, spreadsheet_id, params, sheet_id)
            elif action_name == "unprotect_range":
                _exec_unprotect_range(service, spreadsheet_id, params, sheet_id)
            elif action_name == "clear_sheet":
                _exec_clear_sheet(service, spreadsheet_id, params, sheet_id)
            elif action_name == "scaffold_oppm_form":
                summary = _exec_scaffold_oppm_form(service, spreadsheet_id, params, sheet_id, sheet_title, sa_info=sa_info)
                results.append({"action": action_name, "success": True, "error": None, "summary": summary})
                continue
            elif action_name == "upload_asset_to_drive":
                upload = _exec_upload_asset_to_drive(service, spreadsheet_id, params, sheet_title, sa_info=sa_info)
                results.append({"action": action_name, "success": True, "error": None, "summary": upload})
                continue
            results.append({"action": action_name, "success": True, "error": None})
        except Exception as e:
            logger.warning("execute_actions: action '%s' failed: %s", action_name, e)
            results.append({"action": action_name, "success": False, "error": str(e)})

    return results
