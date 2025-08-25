#!/usr/bin/env python3
"""
Comprehensive API Alignment Fix Script
Fixes both backend and frontend to use consistent naming
"""

import os
import re
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple

# Define the project root
PROJECT_ROOT = Path(__file__).parent.parent
ROUTERS_DIR = PROJECT_ROOT / "api" / "routers"
FRONTEND_API_DIR = PROJECT_ROOT / "frontend" / "lib" / "api"
MAIN_PY = PROJECT_ROOT / "main.py"

class APIAlignmentFixer:
    def __init__(self):
        self.changes = []
        self.backend_endpoints = {}
        self.frontend_endpoints = {}
        
    def analyze_backend(self):
        """Analyze all backend endpoints"""
        print("🔍 Analyzing Backend Endpoints...")
        
        # Parse main.py to get router registrations
        with open(MAIN_PY, 'r') as f:
            main_content = f.read()
        
        # Find all router registrations
        router_pattern = r'app\.include_router\(([^,]+)\.router,\s*prefix="([^"]+)"'
        routers = re.findall(router_pattern, main_content)
        
        for router_name, prefix in routers:
            router_file = ROUTERS_DIR / f"{router_name}.py"
            if router_file.exists():
                endpoints = self.extract_backend_endpoints(router_file, prefix)
                self.backend_endpoints[router_name] = {
                    'prefix': prefix,
                    'endpoints': endpoints
                }
        
        return self.backend_endpoints
    
    def extract_backend_endpoints(self, filepath: Path, prefix: str) -> List[Dict]:
        """Extract endpoints from a router file"""
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Find all endpoint decorators
        endpoint_pattern = r'@router\.(get|post|put|patch|delete)\("([^"]+)"'
        endpoints = re.findall(endpoint_pattern, content)
        
        result = []
        for method, path in endpoints:
            full_path = f"{prefix}{path}" if not path.startswith('/') else f"{prefix}{path}"
            result.append({
                'method': method.upper(),
                'path': path,
                'full_path': full_path,
                'has_trailing_slash': path.endswith('/'),
                'has_underscore': '_' in path and '{' not in path
            })
        
        return result
    
    def analyze_frontend(self):
        """Analyze all frontend API calls"""
        print("🔍 Analyzing Frontend API Calls...")
        
        for service_file in FRONTEND_API_DIR.glob("*.service.ts"):
            endpoints = self.extract_frontend_endpoints(service_file)
            if endpoints:
                self.frontend_endpoints[service_file.stem] = endpoints
        
        return self.frontend_endpoints
    
    def extract_frontend_endpoints(self, filepath: Path) -> List[Dict]:
        """Extract API calls from frontend service file"""
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Pattern to match apiClient calls
        pattern = r'apiClient\.(get|post|put|patch|delete|request|publicGet|publicPost)<[^>]*>\([\'"`]([^\'"`]+)[\'"`]'
        matches = re.findall(pattern, content)
        
        result = []
        for method, endpoint in matches:
            # Check what the endpoint becomes after client.ts transformation
            actual_endpoint = endpoint if endpoint.startswith('/api') else f"/api/v1{endpoint}"
            
            result.append({
                'method': method.upper(),
                'original': endpoint,
                'transformed': actual_endpoint,
                'line': self.get_line_number(content, endpoint)
            })
        
        return result
    
    def get_line_number(self, content: str, search_str: str) -> int:
        """Get line number of a string in content"""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if search_str in line:
                return i
        return 0
    
    def find_mismatches(self):
        """Find mismatches between frontend and backend"""
        print("\n🔍 Finding Mismatches...")
        
        mismatches = {
            'trailing_slash': [],
            'missing_backend': [],
            'missing_frontend': [],
            'path_param_mismatch': []
        }
        
        # Flatten backend endpoints
        all_backend = {}
        for router, data in self.backend_endpoints.items():
            for endpoint in data['endpoints']:
                key = f"{endpoint['method']} {endpoint['full_path']}"
                all_backend[key] = endpoint
        
        # Check each frontend call
        for service, endpoints in self.frontend_endpoints.items():
            for endpoint in endpoints:
                method = endpoint['method']
                path = endpoint['transformed']
                
                # Check exact match
                key = f"{method} {path}"
                if key in all_backend:
                    continue
                
                # Check with trailing slash
                key_slash = f"{method} {path}/"
                if key_slash in all_backend:
                    mismatches['trailing_slash'].append({
                        'service': service,
                        'frontend': path,
                        'backend': f"{path}/",
                        'line': endpoint['line']
                    })
                    continue
                
                # Check for path parameter mismatch
                path_base = re.sub(r'/\d+', '/{id}', path)
                found = False
                for backend_key, backend_endpoint in all_backend.items():
                    if backend_key.startswith(method) and self.paths_match(path, backend_endpoint['full_path']):
                        mismatches['path_param_mismatch'].append({
                            'service': service,
                            'frontend': path,
                            'backend': backend_endpoint['full_path'],
                            'line': endpoint['line']
                        })
                        found = True
                        break
                
                if not found:
                    mismatches['missing_backend'].append({
                        'service': service,
                        'endpoint': endpoint['original'],
                        'method': method,
                        'line': endpoint['line']
                    })
        
        return mismatches
    
    def paths_match(self, frontend_path: str, backend_path: str) -> bool:
        """Check if paths match with parameter substitution"""
        # Replace IDs in frontend path with {param}
        frontend_pattern = re.sub(r'/\d+', '/[^/]+', frontend_path)
        frontend_pattern = re.sub(r'/\$\{[^}]+\}', '/[^/]+', frontend_pattern)
        
        # Replace {param} in backend path with regex
        backend_pattern = re.sub(r'/\{[^}]+\}', '/[^/]+', backend_path)
        
        return frontend_pattern == backend_pattern
    
    def generate_fixes(self, mismatches: Dict):
        """Generate fix recommendations"""
        print("\n📝 Generating Fixes...")
        
        fixes = {
            'backend_fixes': [],
            'frontend_fixes': [],
            'new_endpoints_needed': []
        }
        
        # Fix trailing slashes in backend
        for mismatch in mismatches['trailing_slash']:
            fixes['backend_fixes'].append({
                'type': 'remove_trailing_slash',
                'endpoint': mismatch['backend'],
                'fix_to': mismatch['frontend']
            })
        
        # Fix missing backend endpoints
        for missing in mismatches['missing_backend']:
            fixes['new_endpoints_needed'].append({
                'method': missing['method'],
                'endpoint': missing['endpoint'],
                'service': missing['service']
            })
        
        return fixes
    
    def apply_backend_fixes(self, dry_run: bool = True):
        """Apply fixes to backend files"""
        print("\n🛠️  Applying Backend Fixes...")
        
        if dry_run:
            print("   (DRY RUN - No changes will be made)")
        
        # Fix trailing slashes in router files
        for router_file in ROUTERS_DIR.glob("*.py"):
            with open(router_file, 'r') as f:
                content = f.read()
            
            original = content
            
            # Remove trailing slashes from decorators
            content = re.sub(
                r'(@router\.(get|post|put|patch|delete)\("([^"]+)/"\))',
                r'@router.\2("\3")',
                content
            )
            
            # Fix parameter names to use consistent {id}
            content = re.sub(r'\{session_id\}', '{id}', content)
            content = re.sub(r'\{assessment_id\}', '{id}', content)
            content = re.sub(r'\{profile_id\}', '{id}', content)
            content = re.sub(r'\{policy_id\}', '{id}', content)
            content = re.sub(r'\{evidence_id\}', '{id}', content)
            
            if content != original:
                if not dry_run:
                    with open(router_file, 'w') as f:
                        f.write(content)
                print(f"   ✅ Fixed {router_file.name}")
    
    def generate_report(self, mismatches: Dict, fixes: Dict):
        """Generate detailed report"""
        report = {
            'timestamp': subprocess.check_output(['date', '-Iseconds']).decode().strip(),
            'summary': {
                'total_frontend_endpoints': sum(len(e) for e in self.frontend_endpoints.values()),
                'total_backend_endpoints': sum(len(d['endpoints']) for d in self.backend_endpoints.values()),
                'trailing_slash_issues': len(mismatches['trailing_slash']),
                'missing_backend': len(mismatches['missing_backend']),
                'path_param_mismatches': len(mismatches['path_param_mismatch'])
            },
            'mismatches': mismatches,
            'fixes': fixes
        }
        
        with open(PROJECT_ROOT / 'api-alignment-report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        return report

def main():
    """Main execution"""
    print("🚀 RuleIQ API Alignment Fixer")
    print("=" * 80)
    
    fixer = APIAlignmentFixer()
    
    # Analyze both sides
    backend = fixer.analyze_backend()
    frontend = fixer.analyze_frontend()
    
    # Find mismatches
    mismatches = fixer.find_mismatches()
    
    # Generate fixes
    fixes = fixer.generate_fixes(mismatches)
    
    # Generate report
    report = fixer.generate_report(mismatches, fixes)
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 ANALYSIS SUMMARY\n")
    print(f"Backend Endpoints: {report['summary']['total_backend_endpoints']}")
    print(f"Frontend API Calls: {report['summary']['total_frontend_endpoints']}")
    print(f"Trailing Slash Issues: {report['summary']['trailing_slash_issues']}")
    print(f"Missing Backend Endpoints: {report['summary']['missing_backend']}")
    print(f"Path Parameter Mismatches: {report['summary']['path_param_mismatches']}")
    
    if mismatches['trailing_slash']:
        print("\n⚠️  Trailing Slash Issues:")
        for item in mismatches['trailing_slash'][:5]:
            print(f"   - {item['service']}: {item['frontend']} → {item['backend']}")
    
    if mismatches['missing_backend']:
        print("\n❌ Missing Backend Endpoints:")
        for item in mismatches['missing_backend'][:10]:
            print(f"   - {item['method']} {item['endpoint']} ({item['service']}.ts:{item['line']})")
    
    print("\n" + "=" * 80)
    print("\n📝 RECOMMENDED ACTIONS:\n")
    print("1. Fix trailing slashes in backend (quick win)")
    print("2. Standardize parameter names to use {id}")
    print("3. Implement missing backend endpoints")
    print("4. Update frontend services to match backend patterns")
    
    # Ask to apply fixes
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--fix':
        print("\n🛠️  Applying fixes...")
        fixer.apply_backend_fixes(dry_run=False)
        print("\n✅ Backend fixes applied!")
        print("\n⚠️  Remember to:")
        print("1. Test all endpoints")
        print("2. Update frontend services")
        print("3. Run integration tests")
    else:
        print("\n💡 Run with --fix flag to apply backend fixes automatically")
        print("   python scripts/fix-api-alignment.py --fix")
    
    print(f"\n📄 Detailed report saved to api-alignment-report.json")

if __name__ == "__main__":
    main()