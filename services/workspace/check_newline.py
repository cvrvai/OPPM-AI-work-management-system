import sys
[sys.modules.pop(m, None) for m in list(sys.modules) if 'scaffold' in m or 'fortune' in m]
from domains.oppm.sheet_executor.scaffold import _build_scaffold_actions
from domains.oppm.fortunesheet_builder import _FortuneSheetBuilder

actions = _build_scaffold_actions({'task_count': 10})
builder = _FortuneSheetBuilder()
builder.apply_actions(actions)
sheet = builder.build_sheet()[0]

# Find the metadata cell (row 2, col 7 = H3)
for c in sheet['celldata']:
    if c['r'] == 2 and c['c'] == 7:
        text = c['v'].get('v', '')
        print("Cell value:")
        print(repr(text))
        print("\nDisplayed:")
        print(text)
        break
