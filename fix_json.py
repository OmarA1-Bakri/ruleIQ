#!/usr/bin/env python3
import json
import re

# Read the file
with open('ruleiq_comprehensive_postman_collection.json', 'r') as f:
    content = f.read()

# Fix unescaped newlines in raw JSON bodies
# Pattern to find "raw": "{ ... }" blocks with unescaped newlines
pattern = r'"raw":\s*"(\{[^"]*\})"'

def fix_json_string(match):
    raw_content = match.group(1)
    # Escape newlines and quotes
    escaped = raw_content.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
    return f'"raw": "{escaped}"'

# Apply the fix
content = re.sub(pattern, fix_json_string, content, flags=re.DOTALL)

# Fix the multiline JSON blocks (those with actual newlines)
def fix_multiline_json(content):
    lines = content.split('\n')
    result = []
    in_raw_block = False
    raw_content = []
    raw_prefix = ""
    
    for i, line in enumerate(lines):
        # Check for start of multiline raw JSON - more flexible pattern
        if '"raw": "' in line and (line.strip().endswith('{') or ('{' in line and not line.strip().endswith('"}') and not line.strip().endswith('"},'))):
            # Start of a multiline raw JSON block
            in_raw_block = True
            parts = line.split('"raw": "', 1)
            raw_prefix = parts[0] + '"raw": "'
            raw_content = [parts[1]]
            result.append(raw_prefix)
        elif in_raw_block:
            # Look for end patterns - check if next few lines contain closing
            if line.strip() == '}' and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line == '"' or next_line == '",' or next_line.startswith('}'):
                    # This is the end of the JSON block
                    raw_content.append(line)
                    # Escape the JSON content
                    json_str = '\n'.join(raw_content)
                    escaped = json_str.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
                    result[-1] += escaped + '"'
                    in_raw_block = False
                    raw_content = []
                    raw_prefix = ""
                    continue
            elif line.strip() == '}' and (i + 1 >= len(lines) or lines[i + 1].strip().startswith('}')):
                # End of multiline raw JSON block
                raw_content.append(line)
                # Escape the JSON content
                json_str = '\n'.join(raw_content)
                escaped = json_str.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
                result[-1] += escaped + '"'
                in_raw_block = False
                raw_content = []
                raw_prefix = ""
            elif line.strip() in ['}"', '}",']:
                # Traditional end pattern
                raw_content.append(line.replace('}"', '}').replace('}",', '}'))
                # Escape the JSON content
                json_str = '\n'.join(raw_content)
                escaped = json_str.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
                result[-1] += escaped + '"' + line[line.rfind('}') + 1:]
                in_raw_block = False
                raw_content = []
                raw_prefix = ""
            else:
                raw_content.append(line)
        else:
            result.append(line)
    
    # Handle case where we're still in a raw block at end of file
    if in_raw_block and raw_content:
        json_str = '\n'.join(raw_content)
        escaped = json_str.replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
        result[-1] += escaped + '"'
    
    return '\n'.join(result)

content = fix_multiline_json(content)

# Write the fixed content
with open('ruleiq_comprehensive_postman_collection_fixed.json', 'w') as f:
    f.write(content)

# Validate JSON
try:
    with open('ruleiq_comprehensive_postman_collection_fixed.json', 'r') as f:
        json.load(f)
    print("✅ JSON is now valid!")
except Exception as e:
    print(f"❌ JSON still has issues: {e}")