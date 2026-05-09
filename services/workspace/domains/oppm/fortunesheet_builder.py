"""
fortunesheet_builder.py — Convert scaffold.py actions to FortuneSheet JSON.

This module takes the deterministic action list produced by
sheet_executor/scaffold._build_scaffold_actions() and converts it into
FortuneSheet-compatible sheet data (celldata, borderInfo, merge, columnlen,
rowlen).  This lets the backend generate the exact same visual layout for the
App Editor that scaffold.py produces for Google Sheets.
"""

from typing import Any
import logging

logger = logging.getLogger(__name__)

# ── FortuneSheet style constants ──
_FORTUNE_STYLE_THIN = 1
_FORTUNE_STYLE_MEDIUM = 8


def _col_letters_to_index(letters: str) -> int:
    """A→1, Z→26, AA→27 (1-based)."""
    idx = 0
    for ch in letters.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx


def _parse_cell(cell: str) -> tuple[int, int]:
    """A1 → (row, col) both 1-based."""
    import re
    m = re.match(r"^([A-Z]+)(\d+)$", cell.strip().upper())
    if not m:
        return 0, 0
    return int(m.group(2)), _col_letters_to_index(m.group(1))


def _parse_range(range_str: str) -> tuple[int, int, int, int]:
    """A1:B3 → (r1, c1, r2, c2) all 1-based."""
    parts = range_str.strip().upper().split(":")
    if len(parts) == 1:
        r, c = _parse_cell(parts[0])
        return r, c, r, c
    r1, c1 = _parse_cell(parts[0])
    r2, c2 = _parse_cell(parts[1])
    return r1, c1, r2, c2


def _fortune_border(style: str, color: str, width: int) -> dict:
    """Convert scaffold border style to FortuneSheet border object."""
    style_upper = style.upper() if style else "SOLID"
    if style_upper == "NONE":
        return None
    # Map to FortuneSheet style numbers
    # FortuneSheet: 0=none, 1=thin, 2=hair, 3=dotted, 4=dashed,
    #               5=mdashdot, 8=medium, 7=double, 9=thick
    fortune_style = _FORTUNE_STYLE_THIN
    if style_upper in ("SOLID_MEDIUM", "MEDIUM"):
        fortune_style = _FORTUNE_STYLE_MEDIUM
    elif style_upper == "SOLID_THICK":
        fortune_style = 9
    return {"style": fortune_style, "color": color}


def _make_cell(r: int, c: int, text: str, opts: dict | None = None) -> dict:
    """Build a FortuneSheet cell value object."""
    v: dict[str, Any] = {"v": text, "m": text, "ct": {"fa": "General", "t": "s"}}
    if opts:
        if opts.get("bold"):
            v["bl"] = 1
        if opts.get("fontSize"):
            v["fs"] = opts["fontSize"]
        if opts.get("bg"):
            v["bg"] = opts["bg"]
        if opts.get("hAlign") is not None:
            v["ht"] = opts["hAlign"]
        if opts.get("vAlign") is not None:
            v["vt"] = opts["vAlign"]
        if opts.get("fc"):
            v["fc"] = opts["fc"]
        if opts.get("wrap"):
            v["tb"] = "2"
        if opts.get("rotation"):
            v["tr"] = opts["rotation"]
    return {"r": r, "c": c, "v": v}


def _add_merge(
    merges: dict[str, Any],
    cells: list[dict],
    r: int, c: int,
    rs: int, cs: int,
    text: str,
    opts: dict | None = None,
) -> None:
    """Add a merged cell + fill shadow cells with mc reference."""
    merges[f"{r}_{c}"] = {"r": r, "c": c, "rs": rs, "cs": cs}
    cv = _make_cell(r, c, text, opts)
    cv["v"]["mc"] = {"r": r, "c": c, "rs": rs, "cs": cs}
    cells.append(cv)
    for ri in range(r, r + rs):
        for ci in range(c, c + cs):
            if ri == r and ci == c:
                continue
            cells.append({"r": ri, "c": ci, "v": {"mc": {"r": r, "c": c}}})


def _border_cell(r: int, c: int, sides: dict) -> dict:
    """Build a FortuneSheet borderInfo entry."""
    value: dict[str, Any] = {"row_index": r, "col_index": c}
    for side in ("l", "r", "t", "b"):
        if side in sides and sides[side]:
            value[side] = sides[side]
    return {"rangeType": "cell", "value": value}


def _draw_frame(
    borders: list[dict],
    r1: int, c1: int, r2: int, c2: int,
    style: dict | None = None,
) -> None:
    """Draw outer frame only."""
    s = style or {"style": _FORTUNE_STYLE_MEDIUM, "color": "#000000"}
    for c in range(c1, c2 + 1):
        borders.append(_border_cell(r1, c, {"t": s}))
        borders.append(_border_cell(r2, c, {"b": s}))
    for r in range(r1, r2 + 1):
        borders.append(_border_cell(r, c1, {"l": s}))
        borders.append(_border_cell(r, c2, {"r": s}))


def _draw_grid(
    borders: list[dict],
    r1: int, c1: int, r2: int, c2: int,
    style: dict | None = None,
) -> None:
    """Draw full grid (every cell gets all four sides)."""
    s = style or {"style": _FORTUNE_STYLE_THIN, "color": "#000000"}
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            borders.append(_border_cell(r, c, {"l": s, "r": s, "t": s, "b": s}))


def _draw_hline(
    borders: list[dict],
    row: int, c1: int, c2: int,
    style: dict | None = None,
) -> None:
    """Horizontal line (bottom of row)."""
    s = style or {"style": _FORTUNE_STYLE_MEDIUM, "color": "#000000"}
    for c in range(c1, c2 + 1):
        borders.append(_border_cell(row, c, {"b": s}))


def _draw_vline(
    borders: list[dict],
    col: int, r1: int, r2: int,
    style: dict | None = None,
) -> None:
    """Vertical line (right of column)."""
    s = style or {"style": _FORTUNE_STYLE_MEDIUM, "color": "#000000"}
    for r in range(r1, r2 + 1):
        borders.append(_border_cell(r, col, {"r": s}))


# ════════════════════════════════════════════════════════════
# Action → FortuneSheet converter
# ════════════════════════════════════════════════════════════

class _FortuneSheetBuilder:
    """Accumulates FortuneSheet data from scaffold actions."""

    def __init__(self):
        self.cells: list[dict] = []
        self.borders: list[dict] = []
        self.merges: dict[str, Any] = {}
        self.columnlen: dict[int, int] = {}
        self.rowlen: dict[int, int] = {}
        # Track cell-level formatting so we can merge multiple format actions
        self._cell_format: dict[tuple[int, int], dict] = {}
        # Track which cells have been set (for dedup)
        self._cell_values: dict[tuple[int, int], str] = {}

    def _ensure_cell_format(self, r: int, c: int) -> dict:
        key = (r, c)
        if key not in self._cell_format:
            self._cell_format[key] = {}
        return self._cell_format[key]

    def _flush_cells(self) -> None:
        """Flush accumulated cell formats into the cells list."""
        for (r, c), fmt in self._cell_format.items():
            text = self._cell_values.get((r, c), "")
            # Check if this cell already exists in cells
            existing = None
            for cell in self.cells:
                if cell["r"] == r and cell["c"] == c:
                    existing = cell
                    break
            if existing:
                # Merge format into existing cell
                for k, v in fmt.items():
                    existing["v"][k] = v
            else:
                self.cells.append(_make_cell(r, c, text, fmt))
        self._cell_format.clear()

    def apply_actions(self, actions: list[dict]) -> None:
        """Process a list of scaffold actions."""
        for action in actions:
            name = action.get("action", "")
            params = action.get("params", {})
            handler = getattr(self, f"_handle_{name}", None)
            if handler:
                handler(params)
            else:
                # Unknown action — log and skip
                logger.debug("Unhandled scaffold action: %s", name)
        self._flush_cells()

    # ── Handlers ──

    def _handle_set_value(self, params: dict) -> None:
        range_str = params.get("range", "")
        value = params.get("value", "")
        r1, c1, r2, c2 = _parse_range(range_str)
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                self._cell_values[(r - 1, c - 1)] = str(value) if value is not None else ""
                # If no format exists yet, ensure a basic cell exists
                fmt = self._ensure_cell_format(r - 1, c - 1)

    def _handle_merge_cells(self, params: dict) -> None:
        range_str = params.get("range", "")
        r1, c1, r2, c2 = _parse_range(range_str)
        rs = r2 - r1 + 1
        cs = c2 - c1 + 1
        r0, c0 = r1 - 1, c1 - 1
        text = self._cell_values.get((r0, c0), "")
        fmt = self._cell_format.get((r0, c0), {})
        _add_merge(self.merges, self.cells, r0, c0, rs, cs, text, fmt)
        # Remove the merged cell from pending formats (already flushed)
        self._cell_format.pop((r0, c0), None)

    def _handle_set_border(self, params: dict) -> None:
        range_str = params.get("range", "")
        style = params.get("style", "SOLID")
        color = params.get("color", "#CCCCCC")
        width = params.get("width", 1)
        r1, c1, r2, c2 = _parse_range(range_str)

        # Per-side overrides
        top = _fortune_border(
            params.get("top_style", style),
            params.get("top_color", color),
            params.get("top_width", width),
        )
        bottom = _fortune_border(
            params.get("bottom_style", style),
            params.get("bottom_color", color),
            params.get("bottom_width", width),
        )
        left = _fortune_border(
            params.get("left_style", style),
            params.get("left_color", color),
            params.get("left_width", width),
        )
        right = _fortune_border(
            params.get("right_style", style),
            params.get("right_color", color),
            params.get("right_width", width),
        )
        inner_h = _fortune_border(
            params.get("inner_horizontal_style", style),
            params.get("inner_horizontal_color", color),
            params.get("inner_horizontal_width", width),
        )
        inner_v = _fortune_border(
            params.get("inner_vertical_style", style),
            params.get("inner_vertical_color", color),
            params.get("inner_vertical_width", width),
        )

        # If style is NONE and no per-side overrides, skip
        if style.upper() == "NONE" and not any([top, bottom, left, right, inner_h, inner_v]):
            return

        # Determine if this is a full-grid or frame-only operation
        has_inner = inner_h is not None or inner_v is not None
        is_frame_only = style.upper() == "NONE" and any([top, bottom, left, right]) and not has_inner

        if is_frame_only:
            if top:
                for c in range(c1 - 1, c2):
                    self.borders.append(_border_cell(r1 - 1, c, {"t": top}))
            if bottom:
                for c in range(c1 - 1, c2):
                    self.borders.append(_border_cell(r2 - 1, c, {"b": bottom}))
            if left:
                for r in range(r1 - 1, r2):
                    self.borders.append(_border_cell(r, c1 - 1, {"l": left}))
            if right:
                for r in range(r1 - 1, r2):
                    self.borders.append(_border_cell(r, c2 - 1, {"r": right}))
        else:
            # Full grid
            s = {"style": _FORTUNE_STYLE_THIN, "color": color}
            if style.upper() in ("SOLID_MEDIUM", "MEDIUM"):
                s = {"style": _FORTUNE_STYLE_MEDIUM, "color": color}
            _draw_grid(self.borders, r1 - 1, c1 - 1, r2 - 1, c2 - 1, s)

    def _handle_set_row_height(self, params: dict) -> None:
        start = params.get("start_index", 1)
        end = params.get("end_index", start)
        height = params.get("height", 21)
        for r in range(start, end + 1):
            self.rowlen[r] = height

    def _handle_set_column_width(self, params: dict) -> None:
        start = params.get("start_index", 1)
        end = params.get("end_index", start)
        width = params.get("width", 100)
        for c in range(start, end + 1):
            self.columnlen[c] = width

    def _handle_set_background(self, params: dict) -> None:
        range_str = params.get("range", "")
        color = params.get("color", "#FFFFFF")
        r1, c1, r2, c2 = _parse_range(range_str)
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                fmt = self._ensure_cell_format(r - 1, c - 1)
                fmt["bg"] = color

    def _handle_set_font_size(self, params: dict) -> None:
        range_str = params.get("range", "")
        size = params.get("size", 10)
        r1, c1, r2, c2 = _parse_range(range_str)
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                fmt = self._ensure_cell_format(r - 1, c - 1)
                fmt["fontSize"] = size

    def _handle_set_bold(self, params: dict) -> None:
        range_str = params.get("range", "")
        bold = params.get("bold", True)
        r1, c1, r2, c2 = _parse_range(range_str)
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                fmt = self._ensure_cell_format(r - 1, c - 1)
                if bold:
                    fmt["bold"] = True
                else:
                    fmt.pop("bold", None)

    def _handle_set_alignment(self, params: dict) -> None:
        range_str = params.get("range", "")
        horizontal = params.get("horizontal", "LEFT")
        vertical = params.get("vertical", "MIDDLE")
        r1, c1, r2, c2 = _parse_range(range_str)
        h_map = {"LEFT": 1, "CENTER": 0, "RIGHT": 2}
        v_map = {"TOP": 0, "MIDDLE": 0, "BOTTOM": 2}
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                fmt = self._ensure_cell_format(r - 1, c - 1)
                fmt["hAlign"] = h_map.get(horizontal.upper(), 1)
                fmt["vAlign"] = v_map.get(vertical.upper(), 0)

    def _handle_set_text_wrap(self, params: dict) -> None:
        range_str = params.get("range", "")
        mode = params.get("mode", "WRAP")
        r1, c1, r2, c2 = _parse_range(range_str)
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                fmt = self._ensure_cell_format(r - 1, c - 1)
                if mode.upper() == "WRAP":
                    fmt["wrap"] = True
                else:
                    fmt.pop("wrap", None)

    def _handle_set_text_rotation(self, params: dict) -> None:
        range_str = params.get("range", "")
        angle = params.get("angle", 0)
        r1, c1, r2, c2 = _parse_range(range_str)
        # FortuneSheet rotation: '4' = 90° rotated text
        rotation = "4" if angle == 90 else str(angle)
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                fmt = self._ensure_cell_format(r - 1, c - 1)
                fmt["tr"] = rotation

    def _handle_clear_sheet(self, _params: dict) -> None:
        # No-op for FortuneSheet — we start fresh anyway
        pass

    def _handle_freeze_rows(self, _params: dict) -> None:
        # FortuneSheet doesn't support freeze via JSON config in the same way
        pass

    def build_sheet(self, name: str = "OPPM", version: str = "backend-v1") -> list[dict]:
        """Return the final FortuneSheet sheet array."""
        # Deduplicate borders: keep only the last border for each (row, col, side)
        border_map: dict[tuple[int, int, str], dict] = {}
        for b in self.borders:
            v = b["value"]
            r, c = v["row_index"], v["col_index"]
            for side in ("l", "r", "t", "b"):
                if side in v:
                    border_map[(r, c, side)] = {"rangeType": "cell", "value": {"row_index": r, "col_index": c, side: v[side]}}
        # Merge borders for same cell
        merged_borders: dict[tuple[int, int], dict] = {}
        for (r, c, side), b in border_map.items():
            key = (r, c)
            if key not in merged_borders:
                merged_borders[key] = {"rangeType": "cell", "value": {"row_index": r, "col_index": c}}
            merged_borders[key]["value"][side] = b["value"][side]
        deduped_borders = list(merged_borders.values())

        # Compute dimensions
        max_row = 0
        max_col = 0
        for cell in self.cells:
            max_row = max(max_row, cell["r"])
            max_col = max(max_col, cell["c"])
        # Add buffer
        max_row += 5
        max_col += 5

        return [{
            "name": name,
            "celldata": self.cells,
            "config": {
                "borderInfo": deduped_borders,
                "merge": self.merges,
                "columnlen": self.columnlen,
                "rowlen": self.rowlen,
            },
            "row": max_row,
            "column": max_col,
            "oppmGeneratedLayoutVersion": version,
        }]


# ════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════

def build_fortunesheet_from_scaffold(params: dict | None = None) -> list[dict]:
    """Build a FortuneSheet-compatible OPPM scaffold from backend data.

    Args:
        params: Scaffold parameters (title, leader, objective, deliverable,
                start_date, deadline, task_count, etc.).
                If None, uses all defaults.

    Returns:
        FortuneSheet sheet data array (single sheet).
    """
    from .sheet_executor.scaffold import _build_scaffold_actions

    actions = _build_scaffold_actions(params or {})
    builder = _FortuneSheetBuilder()
    builder.apply_actions(actions)
    return builder.build_sheet()
