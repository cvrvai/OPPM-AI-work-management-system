import sys
for mod in list(sys.modules.keys()):
    if 'scaffold' in mod or 'fortunesheet' in mod:
        del sys.modules[mod]

from domains.oppm.sheet_executor.scaffold import _build_scaffold_actions
from domains.oppm.fortunesheet_builder import _parse_range

actions = _build_scaffold_actions({'task_count': 24})
border_actions = [a for a in actions if a['action'] == 'set_border']

# Find actions that affect row 7, col N (14 in 1-based)
target_row = 7
target_col = 14

for i, a in enumerate(border_actions):
    params = a['params']
    range_str = params['range']
    r1, c1, r2, c2 = _parse_range(range_str)
    if r1 <= target_row <= r2 and c1 <= target_col <= c2:
        print(f'{i}: {range_str} -> style={params.get("style")}, color={params.get("color")}')
