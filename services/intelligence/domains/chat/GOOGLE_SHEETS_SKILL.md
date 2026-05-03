# Google Sheets API Skill Reference for OPPM AI

## Overview

This document teaches the OPPM AI how to control Google Sheets via the Google Sheets API v4. It covers:
1. Cell addressing (A1 notation, R1C1, GridRange)
2. All formatting operations (borders, fonts, colors, alignment)
3. Formula syntax and common functions
4. The math behind borders, ranges, and cell positioning

---

## 1. Cell Addressing Systems

### A1 Notation (what humans use)
- Column letters + row number: `A1`, `B2`, `AA100`
- Range: `A1:B2` (top-left to bottom-right)
- Column A=1, B=2, ... Z=26, AA=27, AB=28, etc.
- **Math**: Column number to letters:
  ```
  letters = ""
  while n > 0:
    n, r = divmod(n - 1, 26)
    letters = chr(65 + r) + letters
  ```

### GridRange (what the API uses)
The Google Sheets API uses 0-based integer coordinates:
```json
{
  "sheetId": 1234567890,
  "startRowIndex": 0,    // row 1 in A1
  "endRowIndex": 5,      // row 5 in A1 (exclusive)
  "startColumnIndex": 0, // column A
  "endColumnIndex": 2    // column C (exclusive)
}
```
- **startRowIndex**: 0-based, inclusive
- **endRowIndex**: 0-based, exclusive
- **startColumnIndex**: 0-based, inclusive
- **endColumnIndex**: 0-based, exclusive
- To target a single cell: `startRowIndex=0, endRowIndex=1, startColumnIndex=0, endColumnIndex=1` = cell A1

### R1C1 Notation (alternative)
- `R1C1` = row 1, column 1 = A1
- `R2C3` = row 2, column 3 = C2
- Used in some formula contexts

---

## 2. Border Math

### Border Structure
Every cell has 4 borders + 2 inner borders:
- **top**: border above the cell
- **bottom**: border below the cell
- **left**: border left of the cell
- **right**: border right of the cell
- **innerHorizontal**: border between this cell and the one below (for ranges)
- **innerVertical**: border between this cell and the one to the right (for ranges)

### Border Style Properties
Each border has:
1. **style**: NONE, DOTTED, DASHED, SOLID, SOLID_MEDIUM, SOLID_THICK, DOUBLE
2. **width**: 1 (thin), 2 (medium), 3 (thick) — in pixels
3. **color**: hex code like #000000 (black), #CCCCCC (light gray)

### Border Overlap Rule
When two adjacent cells both have borders on their shared edge:
- The **thicker** border wins
- If same thickness, the **darker** color wins
- If one is NONE, the other wins

### Standard OPPM Border Layout
```
Header rows (1-5):    SOLID, width=1, color=#000000 (black)
Task rows (6+):       SOLID, width=1, color=#CCCCCC (light gray)
Timeline (J-AI):      NONE (no borders)
```

---

## 3. Formula Syntax

### Basic Rules
- All formulas start with `=`
- Use English function names
- Cell references are relative by default (A1, B2)
- Use `$` for absolute references ($A$1, A$1, $A1)

### Common Functions

#### Math
```
=SUM(A1:A10)           // Add all values in range
=AVERAGE(B1:B10)       // Average of range
=MAX(C1:C10)           // Maximum value
=MIN(D1:D10)           // Minimum value
=COUNT(E1:E10)         // Count numeric cells
=COUNTA(F1:F10)        // Count non-empty cells
=ROUND(G1, 2)          // Round to 2 decimal places
=ABS(H1)               // Absolute value
=MOD(I1, 7)            // Remainder after division
```

#### Text
```
=CONCAT(A1, " ", B1)    // Join text
=LEFT(C1, 3)           // First 3 characters
=RIGHT(D1, 2)          // Last 2 characters
=MID(E1, 2, 5)         // Extract 5 chars starting at position 2
=UPPER(F1)             // Convert to uppercase
=LOWER(G1)             // Convert to lowercase
=TRIM(H1)              // Remove extra spaces
=LEN(I1)               // Count characters
```

#### Date/Time
```
=TODAY()               // Current date
=NOW()                // Current date and time
=YEAR(A1)             // Extract year from date
=MONTH(A1)            // Extract month (1-12)
=DAY(A1)              // Extract day (1-31)
=WEEKDAY(A1)          // Day of week (1=Sunday)
=DATEDIF(A1, B1, "D") // Days between dates
```

#### Logic
```
=IF(A1 > 10, "Yes", "No")           // Conditional
=AND(A1 > 0, B1 > 0)                // Both true
=OR(A1 > 0, B1 > 0)                 // At least one true
=NOT(A1 > 0)                          // Negation
=IFERROR(A1/B1, "Error")             // Handle errors
```

#### Lookup
```
=VLOOKUP("key", A1:C10, 2, FALSE)   // Find "key" in column A, return column B
=HLOOKUP("key", A1:C10, 2, FALSE)   // Find "key" in row 1, return row 2
=MATCH("key", A1:A10, 0)             // Find position of "key"
=INDEX(A1:C10, 2, 3)                 // Get value at row 2, column 3
```

### Formula References
- **Relative**: `A1` — changes when copied
- **Absolute**: `$A$1` — never changes
- **Mixed**: `A$1` or `$A1` — one part changes, one doesn't

---

## 4. Number Format Patterns

```
"#,##0"              // 1,000,000
"#,##0.00"          // 1,000,000.00
"$#,##0.00"         // $1,000,000.00
"0%"                // 50%
"0.00%"             // 50.00%
"yyyy-mm-dd"        // 2026-05-03
"dd-mmm-yyyy"       // 03-May-2026
"hh:mm:ss"          // 14:30:00
"[$-409]#,##0"      // Locale-specific formatting
```

---

## 5. Conditional Formatting Rules

```json
{
  "rule": {
    "type": "NUMBER_GREATER",
    "condition": {
      "values": [{"userEnteredValue": "10"}]
    }
  },
  "format": {
    "backgroundColor": {"red": 1, "green": 0.8, "blue": 0.8}
  }
}
```

Rule types:
- `NUMBER_GREATER`, `NUMBER_LESS`, `NUMBER_EQUAL`
- `TEXT_CONTAINS`, `TEXT_NOT_CONTAINS`
- `BLANK`, `NOT_BLANK`
- `CUSTOM_FORMULA` — use any formula that returns TRUE/FALSE

---

## 6. Data Validation

```json
{
  "range": "A1:A10",
  "rule": {
    "condition": {
      "type": "ONE_OF_LIST",
      "values": [
        {"userEnteredValue": "Option A"},
        {"userEnteredValue": "Option B"}
      ]
    },
    "showCustomUi": true,
    "strict": true
  }
}
```

Validation types:
- `ONE_OF_LIST` — dropdown with specific values
- `NUMBER_GREATER`, `NUMBER_BETWEEN`
- `TEXT_CONTAINS`
- `DATE_IS_VALID` — must be a valid date
- `CUSTOM_FORMULA` — formula must return TRUE

---

## 7. Merge Cells

### Types
- `MERGE_ALL` — merge into one big cell
- `MERGE_COLUMNS` — merge horizontally (same row)
- `MERGE_ROWS` — merge vertically (same column)

### Rules
- Only rectangular ranges can be merged
- Merged cell content = top-left cell's content
- Other cells' content is lost
- To unmerge: `unmergeCells` with the merged range

---

## 8. Protected Ranges

```json
{
  "addProtectedRange": {
    "protectedRange": {
      "range": {
        "sheetId": 123,
        "startRowIndex": 0,
        "endRowIndex": 5,
        "startColumnIndex": 0,
        "endColumnIndex": 38
      },
      "description": "Header rows — do not edit",
      "warningOnly": false
    }
  }
}
```

- `warningOnly: true` — shows warning but allows edit
- `warningOnly: false` — completely blocks editing

---

## 9. Batch Update Request Structure

All formatting changes use `batchUpdate` with a list of requests:

```json
{
  "requests": [
    {
      "updateCells": {
        "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 1},
        "rows": [
          {
            "values": [
              {
                "userEnteredValue": {"stringValue": "Hello"},
                "userEnteredFormat": {
                  "textFormat": {"bold": true, "fontSize": 14},
                  "backgroundColor": {"red": 1, "green": 1, "blue": 1}
                }
              }
            ]
          }
        ],
        "fields": "userEnteredValue,userEnteredFormat"
      }
    },
    {
      "updateBorders": {
        "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 5, "startColumnIndex": 0, "endColumnIndex": 38},
        "top": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}},
        "bottom": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}},
        "left": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}},
        "right": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}}
      }
    }
  ]
}
```

---

## 10. Color Math

Google Sheets API uses RGB values 0-1 (not 0-255):

| Hex | RGB (0-255) | API Value (0-1) |
|-----|-------------|-----------------|
| #000000 | 0, 0, 0 | 0, 0, 0 |
| #FFFFFF | 255, 255, 255 | 1, 1, 1 |
| #FF0000 | 255, 0, 0 | 1, 0, 0 |
| #00FF00 | 0, 255, 0 | 0, 1, 0 |
| #0000FF | 0, 0, 255 | 0, 0, 1 |
| #CCCCCC | 204, 204, 204 | 0.8, 0.8, 0.8 |
| #E8E8E8 | 232, 232, 232 | 0.91, 0.91, 0.91 |
| #1D9E75 | 29, 158, 117 | 0.114, 0.62, 0.459 |
| #EF9F27 | 239, 159, 39 | 0.937, 0.624, 0.153 |
| #E24B4A | 226, 75, 74 | 0.886, 0.294, 0.29 |

**Conversion formula**: `api_value = hex_value / 255`

---

## 11. Common OPPM Patterns

### Set header borders (rows 1-5)
```json
{
  "updateBorders": {
    "range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 5, "startColumnIndex": 0, "endColumnIndex": 38},
    "top": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}},
    "bottom": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}},
    "left": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}},
    "right": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}},
    "innerHorizontal": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}},
    "innerVertical": {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0}}
  }
}
```

### Set task row borders (thin gray)
```json
{
  "updateBorders": {
    "range": {"sheetId": 0, "startRowIndex": 5, "endRowIndex": 100, "startColumnIndex": 0, "endColumnIndex": 38},
    "top": {"style": "SOLID", "width": 1, "color": {"red": 0.8, "green": 0.8, "blue": 0.8}},
    "bottom": {"style": "SOLID", "width": 1, "color": {"red": 0.8, "green": 0.8, "blue": 0.8}},
    "left": {"style": "SOLID", "width": 1, "color": {"red": 0.8, "green": 0.8, "blue": 0.8}},
    "right": {"style": "SOLID", "width": 1, "color": {"red": 0.8, "green": 0.8, "blue": 0.8}}
  }
}
```

### Remove timeline borders (columns J-AI = indices 9-35)
```json
{
  "updateBorders": {
    "range": {"sheetId": 0, "startRowIndex": 5, "endRowIndex": 100, "startColumnIndex": 9, "endColumnIndex": 35},
    "top": {"style": "NONE"},
    "bottom": {"style": "NONE"},
    "left": {"style": "NONE"},
    "right": {"style": "NONE"}
  }
}
```

---

## 12. Error Handling

Common errors and fixes:

| Error | Cause | Fix |
|-------|-------|-----|
| `Invalid JSON payload` | Wrong field name in request | Check API docs for correct field names |
| `Cannot find field` | Extra fields in request | Remove unknown fields |
| `Range exceeds grid bounds` | Range larger than sheet | Check sheet dimensions first |
| `Cannot merge overlapping ranges` | Merge conflicts | Unmerge existing merges first |
| `Invalid values[0][0]: struct_value` | Wrong value type | Use `stringValue`, `numberValue`, `boolValue` |
| `You do not have permission` | Sheet not shared | Share with service account email |

---

## 13. Quick Reference: Action to API Mapping

| Our Action | API Method | Key Fields |
|------------|-----------|------------|
| `set_value` | `values().update()` | `range`, `valueInputOption: USER_ENTERED` |
| `set_border` | `batchUpdate(updateBorders)` | `range`, `top/bottom/left/right/innerHorizontal/innerVertical` |
| `set_background` | `batchUpdate(updateCells)` | `range`, `userEnteredFormat.backgroundColor` |
| `set_font_size` | `batchUpdate(updateCells)` | `range`, `userEnteredFormat.textFormat.fontSize` |
| `set_bold` | `batchUpdate(updateCells)` | `range`, `userEnteredFormat.textFormat.bold` |
| `set_alignment` | `batchUpdate(updateCells)` | `range`, `userEnteredFormat.horizontalAlignment` |
| `set_text_wrap` | `batchUpdate(updateCells)` | `range`, `userEnteredFormat.wrapStrategy` |
| `set_number_format` | `batchUpdate(updateCells)` | `range`, `userEnteredFormat.numberFormat` |
| `merge_cells` | `batchUpdate(mergeCells)` | `range`, `mergeType` |
| `unmerge_cells` | `batchUpdate(unmergeCells)` | `range` |
| `set_row_height` | `batchUpdate(updateDimensionProperties)` | `dimension: ROWS`, `pixelSize` |
| `set_column_width` | `batchUpdate(updateDimensionProperties)` | `dimension: COLUMNS`, `pixelSize` |
| `clear_sheet` | Multiple calls | `values().clear()`, `batchUpdate(unmergeCells)`, `batchUpdate(updateCells)` |

---

*This reference is used by the OPPM AI to generate correct Google Sheets API calls.*
