#!/usr/bin/env python3
"""
Backend API Endpoint Alignment Script
Fixes trailing slashes and standardizes endpoint naming
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Tuple

# Define the project root
PROJECT_ROOT = Path(__file__).parent.parent
ROUTERS_DIR = PROJECT_ROOT / "api" / "routers"

# Mapping of old patterns to new patterns
ENDPOINT_MAPPINGS = {
    # Remove trailing slashes
    r'@router\.(get|post|put|patch|delete)\("([^"]+)/"\)': r'@router.\1("\2")',
    r'@router\.(get|post|put|patch|delete)\("([^"]+)/",': r'@router.\1("\2",',
    
    # Standardize ID parameters
    r'\{session_id\}': '{id}',
    r'\{assessment_id\}': '{id}',
    r'\{profile_id\}': '{id}',
    r'\{policy_id\}': '{id}',
    r'\{framework_id\}': '{id}',
    r'\{user_id\}': '{id}',  # Keep for user-specific routes
    
    # Fix specific naming issues
    r'/business_profiles': '/business-profiles',
    r'/evidence_collection': '/evidence-collection',
    r'/self_review': '/self-review',
}

# Files to process
ROUTER_FILES = [
    "assessments.py",
    "business_profiles.py", 
    "policies.py",
    "evidence.py",
    "frameworks.py",
    "compliance.py",
    "chat.py",
    "implementation.py",
    "integrations.py",
    "monitoring.py",
    "reports.py",
    "dashboard.py",
    "auth.py",
    "ai_chat.py",
    "ai_assessments.py",
    "iq_agent.py",
]

def analyze_router_file(filepath: Path) -> Dict:
    """Analyze a router file for endpoints"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find all endpoint decorators
    endpoint_pattern = r'@router\.(get|post|put|patch|delete)\("([^"]+)"[^)]*\)'
    endpoints = re.findall(endpoint_pattern, content)
    
    # Find router prefix
    prefix_pattern = r'router\s*=\s*APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)["\']'
    prefix_match = re.search(prefix_pattern, content)
    prefix = prefix_match.group(1) if prefix_match else ""
    
    return {
        'file': filepath.name,
        'prefix': prefix,
        'endpoints': [(method.upper(), path) for method, path in endpoints],
        'issues': analyze_issues(endpoints)
    }

def analyze_issues(endpoints: List[Tuple[str, str]]) -> List[str]:
    """Identify issues with endpoints"""
    issues = []
    
    for method, path in endpoints:
        if path.endswith('/'):
            issues.append(f"Trailing slash: {method} {path}")
        
        if '{session_id}' in path or '{assessment_id}' in path:
            issues.append(f"Non-standard ID param: {method} {path}")
        
        if '_' in path and not path.startswith('{'):
            issues.append(f"Underscore in path: {method} {path}")
    
    return issues

def fix_router_file(filepath: Path, dry_run: bool = True) -> Tuple[str, List[str]]:
    """Fix issues in a router file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    changes = []
    
    # Apply all mappings
    for pattern, replacement in ENDPOINT_MAPPINGS.items():
        matches = re.findall(pattern, content)
        if matches:
            content = re.sub(pattern, replacement, content)
            changes.append(f"Applied pattern: {pattern}")
    
    # Fix router prefix if needed
    prefix_pattern = r'(router\s*=\s*APIRouter\([^)]*prefix\s*=\s*["\'])([^"\']+/)["\']'
    prefix_match = re.search(prefix_pattern, content)
    if prefix_match and prefix_match.group(2).endswith('/'):
        new_prefix = prefix_match.group(2).rstrip('/')
        content = re.sub(
            prefix_pattern,
            rf'\1{new_prefix}"',
            content
        )
        changes.append(f"Removed trailing slash from prefix: {prefix_match.group(2)}")
    
    if content != original_content:
        if not dry_run:
            with open(filepath, 'w') as f:
                f.write(content)
        
    return content, changes

def main():
    """Main execution"""
    print("🔍 Analyzing Backend API Endpoints\n")
    print("=" * 80)
    
    all_issues = []
    all_endpoints = {}
    
    # Analyze all router files
    for filename in ROUTER_FILES:
        filepath = ROUTERS_DIR / filename
        if filepath.exists():
            analysis = analyze_router_file(filepath)
            all_endpoints[filename] = analysis
            
            if analysis['issues']:
                print(f"\n📁 {filename}")
                print(f"   Prefix: {analysis['prefix']}")
                print(f"   Issues found: {len(analysis['issues'])}")
                for issue in analysis['issues']:
                    print(f"   - {issue}")
                    all_issues.append((filename, issue))
    
    if not all_issues:
        print("\n✅ No issues found! All endpoints follow standards.")
        return
    
    print("\n" + "=" * 80)
    print(f"\n📊 Total Issues Found: {len(all_issues)}")
    
    # Auto-fix in non-interactive mode
    import sys
    response = sys.argv[1] if len(sys.argv) > 1 else 'n'
    
    if response.lower() == 'y':
        print("\n🛠️  Fixing issues...")
        
        for filename in ROUTER_FILES:
            filepath = ROUTERS_DIR / filename
            if filepath.exists():
                _, changes = fix_router_file(filepath, dry_run=False)
                if changes:
                    print(f"\n✅ Fixed {filename}:")
                    for change in changes:
                        print(f"   - {change}")
        
        print("\n✅ All issues fixed!")
        print("\n📝 Next steps:")
        print("1. Review the changes with 'git diff'")
        print("2. Test the API endpoints")
        print("3. Update frontend services to match")
    else:
        print("\n📝 Dry run mode - no changes made")
        print("Run with confirmation to apply fixes")
    
    # Generate summary report
    with open(PROJECT_ROOT / "api-alignment-backend-report.json", 'w') as f:
        json.dump({
            'total_files': len(ROUTER_FILES),
            'files_with_issues': len([f for f, a in all_endpoints.items() if a.get('issues')]),
            'total_issues': len(all_issues),
            'endpoints': all_endpoints
        }, f, indent=2)
    
    print(f"\n📄 Report saved to api-alignment-backend-report.json")

if __name__ == "__main__":
    main()