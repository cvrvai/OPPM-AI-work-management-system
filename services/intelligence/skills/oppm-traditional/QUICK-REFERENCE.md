# OPPM Traditional Skill — AI Quick Reference

> **For:** AI agent reading this during skill execution
> **Purpose:** Quick lookup of all references, rules, and examples
> **Files in this skill:**
> - `skill.yaml` — Skill definition, triggers, system prompt
> - `template.yaml` — Layout rules (rows, columns, borders, fonts)
> - `sheet-actions.yaml` — Complete action API with parameters and examples
> - `examples/*.json` — Few-shot examples for common scenarios

---

## How to Use These References

### When generating actions, ALWAYS follow this order:

1. **Check `sheet-actions.yaml`** for the action definition
   - What parameters does it need?
   - What are the defaults and enums?
   - What does the example show?

2. **Check `template.yaml`** for exact values
   - What are the standard widths, heights, colors?
   - What font size and alignment for this section?

3. **Check `sheet-actions.yaml` error_prevention rules**
   - Am I about to make a common mistake?
   - Is there a rule that prevents this?

4. **Check `examples/*.json`** for similar scenarios
   - How did the AI handle "make it standard" before?
   - What actions were generated for "add task"?

---

## Quick Value Lookup

### Standard Dimensions
| Element | Value | Source |
|---------|-------|--------|
| Sub-objective columns (B-G) | 40px | template.yaml columns |
| Separator (H) | 10px | template.yaml columns |
| Task number (I) | 50px | template.yaml columns |
| Task title (J) | 280px | template.yaml columns |
| Timeline (K-AJ) | 25px each | template.yaml columns |
| Owner slots (AK-AM) | 80px each | template.yaml columns |
| Task row height | 21px | template.yaml row_heights |
| Header rows | 2-6 | template.yaml rows.header |

### Standard Colors
| Element | Color | Source |
|---------|-------|--------|
| Header borders | #000000 (black) | template.yaml borders.header |
| Task borders | #CCCCCC (gray) | template.yaml borders.task_area |
| Timeline borders | NONE | template.yaml borders.timeline |
| Header background | #E8E8E8 | template.yaml backgrounds.header_row_6 |
| Timeline on-track | #1D9E75 (green) | template.yaml backgrounds.timeline_on_track |
| Timeline at-risk | #EF9F27 (yellow) | template.yaml backgrounds.timeline_at_risk |
| Timeline late | #E24B4A (red) | template.yaml backgrounds.timeline_late |

### Standard Fonts
| Element | Size | Bold | Align | Source |
|---------|------|------|-------|--------|
| Title (row 2) | 14 | yes | CENTER | template.yaml fonts.project_title |
| Leader (row 3) | 11 | yes | — | template.yaml fonts.project_leader |
| Objective (row 4) | 10 | no | — | template.yaml fonts.project_objective |
| Dates (row 5) | 10 | no | — | template.yaml fonts.dates |
| Headers (row 6) | 10 | yes | — | template.yaml fonts.column_headers |
| Task number (I) | 10 | yes | CENTER | template.yaml fonts.task_number |
| Task title (J) | 10 | no | LEFT | template.yaml fonts.task_title |
| Sub-obj checks (B-G) | 10 | no | CENTER | template.yaml fonts.sub_objective_check |
| Owner slots (AK-AM) | 10 | no | CENTER | template.yaml fonts.owner_slot |

---

## Critical Error Prevention Rules

### ❌ NEVER DO THESE

| # | Rule | Why | Fix |
|---|------|-----|-----|
| 1 | Add borders to timeline (K-AJ) | Dots need clean white background | Always set_border style=NONE on K7:AJ{N} |
| 2 | Use black borders on task rows | Gray is less visually heavy | Always use #CCCCCC for task rows |
| 3 | Use gray borders on header | Header needs strong separation | Always use #000000 for header |
| 4 | Put content in column H | It's a separator, not content | Never set values in column H |
| 5 | Use WRAP for task titles | Expands row height, breaks spacing | Always use CLIP for J column |
| 6 | Forget to freeze rows 2-6 | Header must stay visible | Always freeze_rows row_count=6 |
| 7 | Set borders before values | Can interfere with value setting | Order: set_value → set_alignment → set_border |
| 8 | Guess row numbers | Use template reference for exact values | Check template.yaml for row definitions |

---

## Common Action Sequences

### Make It Standard
```
1. set_border style=NONE on B7:AJ{N}
2. set_border style=SOLID #CCCCCC on B7:AJ{N}
3. set_border style=NONE on K7:AJ{N}
4. set_border style=SOLID #000000 on B2:AJ6
5. set_background #E8E8E8 on B6:AJ6
6. set_row_height 21 on rows 7-{N}
7. set_column_width 40 on B-G, 10 on H, 50 on I, 280 on J, 25 on K-AJ, 80 on AK-AM
8. set_font_size 14 on B2:AJ2, 11 on B3:AJ3, 10 on B4:AJ6
9. set_bold true on B2:AJ3, B6:AJ6
10. set_alignment CENTER on B2:AJ2, I7:I{N}, B7:G{N}, AK7:AM{N}
11. set_alignment LEFT on J7:J{N}
12. set_text_wrap CLIP on J7:J{N}
13. freeze_rows 6
```

### Add Task
```
1. set_value on I{row}: "{task_number}"
2. set_value on J{row}: "{task_title}"
3. set_border SOLID #CCCCCC on B{row}:AJ{row}
4. set_border NONE on K{row}:AJ{row}
5. set_font_size 10 on I{row}:J{row}
6. set_bold true on I{row}
7. set_alignment CENTER on I{row}
8. set_alignment LEFT on J{row}
9. set_text_wrap CLIP on J{row}
10. set_row_height 21 on row {row}
```

### Update Timeline
```
1. set_value on {cell}: "●" (or other marker)
2. set_alignment CENTER on {cell}
3. set_text_color {status_color} on {cell}
```

### Recreate Form (Preferred: Scaffold)
```
1. scaffold_oppm_form with project metadata
   → Produces complete form in ONE action
```

---

## Action Parameter Quick Reference

### set_border
```yaml
range: "A1:AI5"           # Required
style: "SOLID"              # SOLID | NONE | DOTTED | DASHED
color: "#000000"            # Hex color
width: 1                    # 1=thin, 2=medium, 3=thick
# Per-side overrides (optional):
top_style: "SOLID"
top_color: "#000000"
top_width: 2
# Same for bottom, left, right, inner_horizontal, inner_vertical
```

### set_value
```yaml
range: "G1"                 # Required
value: "Project Leader: X"  # Required, use \n for newlines
```

### set_font_size
```yaml
range: "A1:AI1"            # Required
size: 14                    # Required
```

### set_bold
```yaml
range: "A1:AI2"             # Required
bold: true                  # Required
```

### set_alignment
```yaml
range: "A1:AI1"             # Required
horizontal: "CENTER"        # LEFT | CENTER | RIGHT
vertical: "MIDDLE"          # TOP | MIDDLE | BOTTOM
```

### set_text_wrap
```yaml
range: "I6:I30"             # Required
mode: "CLIP"                # CLIP | WRAP | OVERFLOW_CELL
```

### set_row_height
```yaml
start_index: 6              # Required (1-based row)
end_index: 30               # Required (inclusive)
height: 21                  # Required (pixels)
```

### set_column_width
```yaml
start_index: 1              # Required (1-based: 1=A, 2=B...)
end_index: 6                # Required (inclusive)
width: 40                   # Required (pixels)
```

### merge_cells
```yaml
range: "G3:AI4"             # Required
```

### freeze_rows
```yaml
row_count: 5                # Required
```

---

## Examples Directory

| File | Scenario | Actions |
|------|----------|---------|
| `fill_form.json` | Create OPPM from scratch | 25+ actions |
| `make_standard.json` | Fix formatting on existing form | 16 actions |
| `add_border.json` | Add borders to task rows | 2 actions |
| `recreate.json` | Delete and rebuild | 25+ actions |
| `fix_borders.json` | Fix incorrect borders | 3 actions |
| `make_standard_reference.json` | Make standard using references | 16 actions |
| `add_task_reference.json` | Add task using references | 10 actions |
| `update_timeline_reference.json` | Update timeline using references | 3 actions |
| `scaffold_form.json` | Recreate using scaffold | 1 action |

---

## Decision Tree

```
User says...
├── "create the OPPM" / "fill the form"
│   └── Use scaffold_oppm_form (1 action) OR fill_form sequence
├── "make it standard" / "fix formatting"
│   └── Use make_standard sequence (13 actions)
├── "add task X: ..."
│   └── Use add_task sequence (10 actions)
├── "mark task X as [status] for week Y"
│   └── Use update_timeline sequence (3 actions)
├── "delete and recreate"
│   └── Use scaffold_oppm_form (1 action) OR clear_sheet + rebuild
├── "add border to..."
│   └── Use set_border with correct color (#CCCCCC for tasks, #000000 for header)
├── "remove border from..."
│   └── Use set_border style=NONE
└── "update [field]"
    └── Use set_value on the specific cell
```

---

## Remember

1. **ALWAYS check references first** — Never guess values
2. **ALWAYS follow error_prevention rules** — They prevent common mistakes
3. **ALWAYS use the correct sequence** — Order matters (values before borders)
4. **ALWAYS remove timeline borders** — After applying task borders
5. **ALWAYS freeze rows 2-6** — After rebuilding header (leave row 1 empty)
6. **PREFER scaffold_oppm_form** — For full-form recreation (1 action vs 80+)

---

*Last updated: 2026-05-07*
*Skill version: 1.0*
