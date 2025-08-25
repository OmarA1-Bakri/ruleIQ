#!/usr/bin/env python3
"""
Fix JSON parsing errors in comprehensive Postman collections
Addresses duplicate keys, malformed structures, and syntax errors
"""
import json
import re
import sys
from pathlib import Path

def fix_json_file(filepath):
    """Fix common JSON errors in Postman collections"""
    print(f"🔧 Fixing JSON errors in: {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix 1: Remove duplicate "raw" keys
        # Pattern: "raw": "...", "raw": "..." -> "raw": "..."
        content = re.sub(r'"raw":\s*"[^"]*",\s*"raw":', '"raw":', content)
        
        # Fix 2: Fix malformed body structures
        # Look for patterns like: "raw": "{{base_url}}/api/v1/...
        content = re.sub(
            r'"raw":\s*"([^"]*)\\\",\\n\s*\\"host\\".*?\\"path\\".*?\]\\n\s*\}"',
            r'"raw": "\1"',
            content,
            flags=re.MULTILINE | re.DOTALL
        )
        
        # Fix 3: Clean up escaped quotes in raw strings
        content = re.sub(r'\\"', '"', content)
        
        # Fix 4: Remove trailing commas before closing braces/brackets
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # Fix 5: Fix empty raw bodies
        content = re.sub(r'"raw":\s*"\s*"', '"raw": ""', content)
        
        # Validate JSON structure
        try:
            json_data = json.loads(content)
            print(f"✅ JSON structure validated successfully")
            
            # Write fixed version
            output_path = filepath.replace('.json', '_repaired.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Repaired file saved as: {output_path}")
            return output_path, len(json_data.get('item', []))
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON validation failed after fixes: {e}")
            # Save intermediate version for manual inspection
            debug_path = filepath.replace('.json', '_debug.json')
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"📋 Debug file saved as: {debug_path}")
            return None, 0
            
    except Exception as e:
        print(f"❌ Error processing file: {e}")
        return None, 0

def main():
    """Fix all comprehensive Postman collection files"""
    files_to_fix = [
        'ruleiq_comprehensive_postman_collection_fixed.json',
        'ruleiq_comprehensive_postman_collection_v2.json'
    ]
    
    results = []
    for filename in files_to_fix:
        filepath = f'/home/omar/Documents/ruleIQ/{filename}'
        if Path(filepath).exists():
            output_path, endpoint_count = fix_json_file(filepath)
            if output_path:
                results.append((output_path, endpoint_count))
    
    # Summary
    print(f"\n📊 JSON Repair Summary:")
    for output_path, count in results:
        print(f"✅ {Path(output_path).name}: {count} endpoints ready for testing")
    
    return results

if __name__ == "__main__":
    main()