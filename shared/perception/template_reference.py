"""TemplateReference — loads and queries OPPM template definitions from YAML.

This class gives the AI a structured, programmatic understanding of the OPPM
template so it never guesses row numbers, column widths, or border colors.

Accessible to all services via `shared.perception.TemplateReference`.

Usage:
    from shared.perception import TemplateReference
    template = TemplateReference("services/intelligence/skills/oppm-traditional/template.yaml")
    border_rule = template.get_border_rule("header")
    font_rule = template.get_font_rule("project_title")
    warnings = template.validate_action({"action": "set_border", "params": {"range": "J6:AI10", "style": "SOLID"}})
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

logger = logging.getLogger(__name__)

# Fallback YAML parser if PyYAML is not installed
def _load_yaml(path: str | Path) -> dict[str, Any]:
    if yaml is not None:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    # Minimal fallback — should not happen in production
    raise RuntimeError("PyYAML is required but not installed")


class TemplateReference:
    """Loads and queries OPPM template definitions from YAML files.

    The template YAML defines:
    - Row/column structure (header rows, task rows, timeline, owners)
    - Border rules (which ranges get which border styles/colors)
    - Font rules (sizes, bold, alignment per element)
    - Background colors
    - Column widths and row heights
    - Content templates
    - Merge rules
    - Validation constraints
    """

    def __init__(self, template_path: str | Path) -> None:
        self._path = Path(template_path)
        if not self._path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        self._data = _load_yaml(self._path)
        logger.debug("Loaded template: %s", self._path)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_metadata(self) -> dict[str, Any]:
        """Return template metadata (name, version, description)."""
        return self._data.get("metadata", {})

    def get_sheet_config(self) -> dict[str, Any]:
        """Return sheet-level config (frozen rows, tab name)."""
        return self._data.get("sheet", {})

    def get_row_definition(self, section: str) -> dict[str, Any] | None:
        """Get row definition for a section (header, task_area, etc.)."""
        rows = self._data.get("rows", {})
        return rows.get(section)

    def get_column_definition(self, column_id: str) -> dict[str, Any] | None:
        """Get column definition by letter (A, B, ..., AL) or range (J:AI)."""
        columns = self._data.get("columns", [])
        for col in columns:
            if col.get("id") == column_id:
                return col
        return None

    def get_column_width(self, column_id: str) -> int | None:
        """Get standard width for a column."""
        col = self.get_column_definition(column_id)
        if col:
            return col.get("width")
        return None

    def get_border_rule(self, section: str) -> dict[str, Any] | None:
        """Get border rule for a section (header, task_area, timeline)."""
        borders = self._data.get("borders", {})
        return borders.get(section)

    def get_font_rule(self, element: str) -> dict[str, Any] | None:
        """Get font rule for an element (project_title, task_number, etc.)."""
        fonts = self._data.get("fonts", {})
        return fonts.get(element)

    def get_background_rule(self, element: str) -> dict[str, Any] | None:
        """Get background color rule for an element."""
        backgrounds = self._data.get("backgrounds", {})
        return backgrounds.get(element)

    def get_row_height(self, section: str) -> int | None:
        """Get standard row height for a section."""
        row_heights = self._data.get("row_heights", {})
        rule = row_heights.get(section)
        if rule:
            return rule.get("height")
        return None

    def get_content_template(self, row_name: str) -> str | None:
        """Get content template for a header row."""
        content = self._data.get("content", {})
        return content.get(row_name)

    def get_merge_rule(self, element: str) -> dict[str, Any] | None:
        """Get merge rule for an element (project_title, column_headers, etc.)."""
        merges = self._data.get("merges", {})
        return merges.get(element)

    def get_validation(self, key: str) -> Any | None:
        """Get validation constraint (max_tasks, max_sub_objectives, etc.)."""
        validation = self._data.get("validation", {})
        return validation.get(key)

    def get_examples(self) -> list[dict[str, Any]]:
        """Get training examples for the AI."""
        return self._data.get("examples", [])

    # ── Summary Builders ────────────────────────────────────────────────────

    def build_border_summary(self) -> str:
        """Build a human-readable summary of border rules for the LLM."""
        borders = self._data.get("borders", {})
        lines = ["### Border Rules"]
        for section, rule in borders.items():
            range_str = rule.get("range", "unknown")
            style = rule.get("style", "unknown")
            color = rule.get("color", "default")
            width = rule.get("width", "default")
            if style == "NONE":
                lines.append(f"- {section} ({range_str}): NO borders")
            else:
                lines.append(f"- {section} ({range_str}): {style}, width={width}, color={color}")
        return "\n".join(lines)

    def build_font_summary(self) -> str:
        """Build a human-readable summary of font rules for the LLM."""
        fonts = self._data.get("fonts", {})
        lines = ["### Font Rules"]
        for element, rule in fonts.items():
            range_str = rule.get("range", "unknown")
            size = rule.get("size", "default")
            bold = rule.get("bold", False)
            align = rule.get("alignment", "default")
            parts = [f"size={size}"]
            if bold:
                parts.append("bold")
            if align != "default":
                parts.append(f"align={align}")
            lines.append(f"- {element} ({range_str}): {', '.join(parts)}")
        return "\n".join(lines)

    def build_column_width_summary(self) -> str:
        """Build a human-readable summary of column widths for the LLM."""
        columns = self._data.get("columns", [])
        lines = ["### Column Widths"]
        for col in columns:
            col_id = col.get("id", "?")
            name = col.get("name", "unknown")
            width = col.get("width", "default")
            lines.append(f"- Column {col_id} ({name}): {width}px")
        return "\n".join(lines)

    def build_row_height_summary(self) -> str:
        """Build a human-readable summary of row heights for the LLM."""
        row_heights = self._data.get("row_heights", {})
        lines = ["### Row Heights"]
        for section, rule in row_heights.items():
            rows = rule.get("rows", "unknown")
            height = rule.get("height", "default")
            lines.append(f"- {section} ({rows}): {height}px")
        return "\n".join(lines)

    def build_template_summary(self) -> str:
        """Build a complete summary of all template rules for injection into LLM prompt."""
        parts = [
            "## OPPM TEMPLATE REFERENCE",
            "",
            self.build_border_summary(),
            "",
            self.build_font_summary(),
            "",
            self.build_column_width_summary(),
            "",
            self.build_row_height_summary(),
            "",
            "### Content Templates",
        ]
        content = self._data.get("content", {})
        for row_name, template in content.items():
            parts.append(f"- {row_name}: {template}")
        return "\n".join(parts)

    # ── Validation ──────────────────────────────────────────────────────────

    def validate_action(self, action: dict[str, Any]) -> list[str]:
        """Validate an action against the template. Returns list of warnings.

        Example warnings:
        - "Timeline area J-AI should have style=NONE"
        - "Column width 100px for column A differs from standard 40px"
        """
        warnings: list[str] = []
        action_type = action.get("action", "")
        params = action.get("params", {})

        if action_type == "set_border":
            warnings.extend(self._validate_border_action(params))
        elif action_type == "set_font_size":
            warnings.extend(self._validate_font_action(params))
        elif action_type == "set_column_width":
            warnings.extend(self._validate_column_width_action(params))
        elif action_type == "set_row_height":
            warnings.extend(self._validate_row_height_action(params))
        elif action_type == "set_background":
            warnings.extend(self._validate_background_action(params))

        return warnings

    def _validate_border_action(self, params: dict[str, Any]) -> list[str]:
        warnings = []
        range_str = params.get("range", "")
        style = params.get("style", "")

        # Check if range overlaps timeline area (J-AI)
        if self._range_overlaps(range_str, "J", "AI"):
            if style != "NONE":
                warnings.append(
                    f"Timeline area {range_str} should have style=NONE (per template). "
                    f"Got style={style}."
                )

        # Check if range is in header area (1-5) and style is not black
        if self._range_in_rows(range_str, 1, 5):
            expected = self.get_border_rule("header")
            if expected:
                expected_color = expected.get("color", "#000000")
                actual_color = params.get("color", "")
                if actual_color and actual_color != expected_color:
                    warnings.append(
                        f"Header border color {actual_color} differs from standard {expected_color}"
                    )

        # Check if range is in task area (6+) and style/color differ from standard
        if self._range_in_rows(range_str, 6, 999):
            expected = self.get_border_rule("task_area")
            if expected:
                expected_color = expected.get("color", "#CCCCCC")
                actual_color = params.get("color", "")
                if actual_color and actual_color != expected_color:
                    warnings.append(
                        f"Task area border color {actual_color} differs from standard {expected_color}"
                    )

        return warnings

    def _validate_font_action(self, params: dict[str, Any]) -> list[str]:
        warnings = []
        range_str = params.get("range", "")
        size = params.get("size", 0)

        # Check if range is in header and size differs from standard
        if self._range_in_rows(range_str, 1, 5):
            fonts = self._data.get("fonts", {})
            for element, rule in fonts.items():
                rule_range = rule.get("range", "")
                if self._ranges_overlap(range_str, rule_range):
                    expected_size = rule.get("size")
                    if expected_size and size != expected_size:
                        warnings.append(
                            f"Font size {size} for {range_str} differs from "
                            f"template standard {expected_size} for {element}"
                        )

        return warnings

    def _validate_column_width_action(self, params: dict[str, Any]) -> list[str]:
        warnings = []
        start_index = params.get("start_index", 0)
        end_index = params.get("end_index", 0)
        width = params.get("width", 0)

        columns = self._data.get("columns", [])
        for col in columns:
            col_index = col.get("index", 0)
            if isinstance(col_index, int) and start_index <= col_index <= end_index:
                expected_width = col.get("width")
                if expected_width and width != expected_width:
                    col_id = col.get("id", "?")
                    warnings.append(
                        f"Column width {width}px for column {col_id} differs from "
                        f"template standard {expected_width}px"
                    )

        return warnings

    def _validate_row_height_action(self, params: dict[str, Any]) -> list[str]:
        warnings = []
        start_index = params.get("start_index", 0)
        end_index = params.get("end_index", 0)
        height = params.get("height", 0)

        # Check task rows
        if start_index >= 6:
            expected = self.get_row_height("task_rows")
            if expected and height != expected:
                warnings.append(
                    f"Row height {height}px for task rows differs from "
                    f"template standard {expected}px"
                )

        return warnings

    def _validate_background_action(self, params: dict[str, Any]) -> list[str]:
        warnings = []
        range_str = params.get("range", "")
        color = params.get("color", "")

        # Check header row 5 background
        if self._range_in_rows(range_str, 5, 5):
            expected = self.get_background_rule("header_row_5")
            if expected:
                expected_color = expected.get("color", "#E8E8E8")
                if color != expected_color:
                    warnings.append(
                        f"Header row 5 background color {color} differs from "
                        f"template standard {expected_color}"
                    )

        return warnings

    # ── Range Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _col_to_index(col: str) -> int:
        """Convert column letter to 1-based index (A=1, B=2, ..., Z=26, AA=27)."""
        result = 0
        for char in col.upper():
            result = result * 26 + (ord(char) - ord("A") + 1)
        return result

    @staticmethod
    def _parse_range(range_str: str) -> tuple[int, int, int, int]:
        """Parse A1 notation range into (start_row, start_col, end_row, end_col).
        All 1-based. Single cell like 'A1' returns (1, 1, 1, 1).
        """
        import re
        _COL_RE = re.compile(r"^([A-Z]+)(\d+)$")

        def _parse_cell(cell: str) -> tuple[int, int]:
            m = _COL_RE.match(cell.strip().upper())
            if not m:
                return 0, 0
            col_letters = m.group(1)
            col_index = 0
            for char in col_letters.upper():
                col_index = col_index * 26 + (ord(char) - ord("A") + 1)
            return int(m.group(2)), col_index

        if ":" not in range_str:
            r, c = _parse_cell(range_str)
            return r, c, r, c

        parts = range_str.strip().upper().split(":")
        r1, c1 = _parse_cell(parts[0])
        r2, c2 = _parse_cell(parts[1])
        return r1, c1, r2, c2

    def _range_overlaps(self, range_str: str, col_start: str, col_end: str) -> bool:
        """Check if range_str overlaps with column range col_start:col_end (any rows)."""
        try:
            _, start_col, _, end_col = self._parse_range(range_str)
            target_start = self._col_to_index(col_start)
            target_end = self._col_to_index(col_end)
            return start_col <= target_end and end_col >= target_start
        except (ValueError, IndexError):
            return False

    def _range_in_rows(self, range_str: str, min_row: int, max_row: int) -> bool:
        """Check if range_str is entirely within min_row:max_row."""
        try:
            start_row, _, end_row, _ = self._parse_range(range_str)
            return start_row >= min_row and end_row <= max_row
        except (ValueError, IndexError):
            return False

    def _ranges_overlap(self, range_a: str, range_b: str) -> bool:
        """Check if two ranges overlap."""
        try:
            a_start_row, a_start_col, a_end_row, a_end_col = self._parse_range(range_a)
            b_start_row, b_start_col, b_end_row, b_end_col = self._parse_range(range_b)
            return (
                a_start_row <= b_end_row and a_end_row >= b_start_row and
                a_start_col <= b_end_col and a_end_col >= b_start_col
            )
        except (ValueError, IndexError):
            return False

    # ── Debug / Introspection ─────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return the full template data as a dict."""
        return self._data

    def __repr__(self) -> str:
        meta = self.get_metadata()
        return f"TemplateReference(name={meta.get('name', 'unknown')}, version={meta.get('version', '?')})"
