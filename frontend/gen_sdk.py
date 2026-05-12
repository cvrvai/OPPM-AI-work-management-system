import re

with open('src/generated/intelligence-api/types.gen.ts', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all Data types with url field using a stack-based brace matcher
def find_data_types(text):
    results = []
    pattern = r'export type (\w+Data) = \{'
    for m in re.finditer(pattern, text):
        start = m.start()
        name = m.group(1)
        # Find matching closing brace
        i = m.end() - 1
        depth = 1
        while i < len(text) and depth > 0:
            i += 1
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
        block = text[m.end()-1:i+1]
        # Extract url from block
        url_match = re.search(r"url: '([^']+)'", block)
        if url_match:
            results.append((name, url_match.group(1)))
    return results

matches = find_data_types(content)

for data_type, url in matches[:15]:
    print(f'{data_type} -> {url}')
print(f'Total matches: {len(matches)}')
