#!/usr/bin/env python3
"""
Analyze and identify duplicate API endpoints in the ruleIQ codebase
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
ROUTERS_DIR = PROJECT_ROOT / "api" / "routers"
MAIN_PY = PROJECT_ROOT / "main.py"

class DuplicateAnalyzer:
    def __init__(self):
        self.endpoints = defaultdict(list)
        self.functionality_map = defaultdict(list)
        
    def analyze_routers(self):
        """Analyze all router files for endpoints"""
        print("🔍 Analyzing Router Files...\n")
        
        # Parse main.py to get router registrations
        with open(MAIN_PY, 'r') as f:
            main_content = f.read()
        
        # Find all router registrations
        router_pattern = r'app\.include_router\(([^,]+)\.router,\s*prefix="([^"]+)"'
        routers = re.findall(router_pattern, main_content)
        
        for router_name, prefix in routers:
            router_file = ROUTERS_DIR / f"{router_name}.py"
            if router_file.exists():
                self.extract_endpoints(router_file, prefix, router_name)
        
        return self.endpoints
    
    def extract_endpoints(self, filepath: Path, prefix: str, router_name: str):
        """Extract endpoints from a router file"""
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Find all endpoint decorators with their function names
        endpoint_pattern = r'@router\.(get|post|put|patch|delete)\("([^"]+)".*?\)\s*(?:async\s+)?def\s+(\w+)'
        matches = re.findall(endpoint_pattern, content, re.DOTALL)
        
        for method, path, function_name in matches:
            full_path = f"{prefix}{path}" if not path.startswith('/') else f"{prefix}{path}"
            endpoint_key = f"{method.upper()} {full_path}"
            
            self.endpoints[endpoint_key].append({
                'router': router_name,
                'function': function_name,
                'file': filepath.name,
                'prefix': prefix,
                'path': path
            })
            
            # Map by functionality
            self.functionality_map[function_name].append({
                'endpoint': endpoint_key,
                'router': router_name
            })
    
    def find_duplicates(self):
        """Find different types of duplicates"""
        duplicates = {
            'exact_duplicates': [],
            'semantic_duplicates': [],
            'namespace_duplicates': [],
            'unused_endpoints': []
        }
        
        # 1. Exact duplicates - same endpoint registered multiple times
        for endpoint, locations in self.endpoints.items():
            if len(locations) > 1:
                duplicates['exact_duplicates'].append({
                    'endpoint': endpoint,
                    'locations': locations
                })
        
        # 2. Semantic duplicates - different endpoints doing same thing
        self.find_semantic_duplicates(duplicates)
        
        # 3. Namespace duplicates - same functionality in different namespaces
        self.find_namespace_duplicates(duplicates)
        
        return duplicates
    
    def find_semantic_duplicates(self, duplicates):
        """Find endpoints that appear to do the same thing"""
        # Group by similar function names
        function_groups = defaultdict(list)
        
        for func_name, endpoints in self.functionality_map.items():
            # Normalize function name for comparison
            normalized = func_name.lower().replace('_', '')
            function_groups[normalized].extend(endpoints)
        
        for normalized, endpoints in function_groups.items():
            if len(endpoints) > 1:
                # Check if they're in different routers
                routers = set(e['router'] for e in endpoints)
                if len(routers) > 1:
                    duplicates['semantic_duplicates'].append({
                        'function_pattern': normalized,
                        'endpoints': endpoints
                    })
    
    def find_namespace_duplicates(self, duplicates):
        """Find same resources exposed through different API namespaces"""
        # Common patterns across namespaces
        namespace_patterns = {
            '/api/v1/': [],
            '/api/admin/': [],
            '/api/ai/': [],
            '/api/freemium/': []
        }
        
        for endpoint, locations in self.endpoints.items():
            for namespace in namespace_patterns:
                if namespace in endpoint:
                    # Extract resource after namespace
                    resource = endpoint.split(namespace)[1].split(' ')[0] if namespace in endpoint else ''
                    namespace_patterns[namespace].append({
                        'endpoint': endpoint,
                        'resource': resource,
                        'locations': locations
                    })
        
        # Find resources that appear in multiple namespaces
        resource_map = defaultdict(list)
        for namespace, endpoints in namespace_patterns.items():
            for ep in endpoints:
                if ep['resource']:
                    resource_map[ep['resource']].append({
                        'namespace': namespace,
                        'endpoint': ep['endpoint']
                    })
        
        for resource, occurrences in resource_map.items():
            if len(occurrences) > 1:
                duplicates['namespace_duplicates'].append({
                    'resource': resource,
                    'occurrences': occurrences
                })
    
    def analyze_usage(self):
        """Analyze which endpoints are actually used by frontend"""
        # Load the API alignment report if it exists
        report_file = PROJECT_ROOT / "api-alignment-report.json"
        if report_file.exists():
            with open(report_file, 'r') as f:
                report = json.load(f)
            
            # Get all backend endpoints
            all_backend = set()
            for endpoint in self.endpoints.keys():
                all_backend.add(endpoint)
            
            # Get frontend calls from mismatches
            frontend_calls = set()
            if 'mismatches' in report:
                for category in report['mismatches'].values():
                    if isinstance(category, list):
                        for item in category:
                            if 'endpoint' in item:
                                frontend_calls.add(item.get('method', 'GET') + ' ' + item['endpoint'])
            
            # Find unused endpoints
            unused = all_backend - frontend_calls
            return list(unused)
        return []
    
    def generate_report(self, duplicates):
        """Generate a detailed report"""
        print("=" * 80)
        print("📊 DUPLICATE ENDPOINT ANALYSIS REPORT")
        print("=" * 80)
        
        # Exact duplicates
        if duplicates['exact_duplicates']:
            print("\n❌ EXACT DUPLICATES (Same endpoint registered multiple times):")
            for dup in duplicates['exact_duplicates']:
                print(f"\n  {dup['endpoint']}:")
                for loc in dup['locations']:
                    print(f"    - {loc['file']} -> {loc['function']}()")
        else:
            print("\n✅ No exact duplicates found")
        
        # Semantic duplicates
        if duplicates['semantic_duplicates']:
            print("\n⚠️  SEMANTIC DUPLICATES (Similar functionality in different routers):")
            for dup in duplicates['semantic_duplicates']:
                print(f"\n  Pattern: {dup['function_pattern']}")
                for ep in dup['endpoints']:
                    print(f"    - {ep['endpoint']} ({ep['router']}.py)")
        else:
            print("\n✅ No semantic duplicates found")
        
        # Namespace duplicates
        if duplicates['namespace_duplicates']:
            print("\n🔄 NAMESPACE DUPLICATES (Same resource in multiple namespaces):")
            for dup in duplicates['namespace_duplicates']:
                print(f"\n  Resource: {dup['resource']}")
                for occ in dup['occurrences']:
                    print(f"    - {occ['endpoint']}")
        else:
            print("\n✅ No namespace duplicates found")
        
        # Unused endpoints
        unused = self.analyze_usage()
        if unused:
            print(f"\n🗑️  POTENTIALLY UNUSED ENDPOINTS ({len(unused)} total):")
            # Show first 20
            for endpoint in sorted(unused)[:20]:
                print(f"    - {endpoint}")
            if len(unused) > 20:
                print(f"    ... and {len(unused) - 20} more")
        
        # Summary
        print("\n" + "=" * 80)
        print("📈 SUMMARY:")
        print(f"  Total endpoints analyzed: {len(self.endpoints)}")
        print(f"  Exact duplicates: {len(duplicates['exact_duplicates'])}")
        print(f"  Semantic duplicates: {len(duplicates['semantic_duplicates'])}")
        print(f"  Namespace duplicates: {len(duplicates['namespace_duplicates'])}")
        print(f"  Potentially unused: {len(unused)}")
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        print("  1. Remove exact duplicates immediately")
        print("  2. Consolidate semantic duplicates where possible")
        print("  3. Review namespace duplicates for consistency")
        print("  4. Verify and remove unused endpoints")
        print("  5. Consider API versioning strategy for namespace organization")
        
        return {
            'total_endpoints': len(self.endpoints),
            'duplicates': duplicates,
            'unused_count': len(unused)
        }

def main():
    analyzer = DuplicateAnalyzer()
    
    # Analyze routers
    endpoints = analyzer.analyze_routers()
    
    # Find duplicates
    duplicates = analyzer.find_duplicates()
    
    # Generate report
    report = analyzer.generate_report(duplicates)
    
    # Save to file
    with open(PROJECT_ROOT / "duplicate-analysis-report.json", 'w') as f:
        json.dump({
            'endpoints': {k: v for k, v in endpoints.items()},
            'duplicates': duplicates,
            'summary': report
        }, f, indent=2)
    
    print(f"\n📄 Detailed report saved to duplicate-analysis-report.json")

if __name__ == "__main__":
    main()