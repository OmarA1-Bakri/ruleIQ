#!/usr/bin/env python3
"""
TODO/FIXME/HACK Scanner for RuleIQ

Scans the codebase for technical debt markers and enforces issue reference policy.
Follows the pattern established by scan_secrets.py.

Usage:
    python scripts/ci/scan_todos.py --format markdown --output TODO_INVENTORY.md
    python scripts/ci/scan_todos.py --enforce --severity CRITICAL --severity HIGH
    python scripts/ci/scan_todos.py --stats-only
"""

import re
import subprocess
import argparse
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from collections import Counter


# Severity mapping for TODO markers
SEVERITY_MAP = {
    'FIXME': 'CRITICAL',
    'BUG': 'CRITICAL',
    'HACK': 'HIGH',
    'XXX': 'HIGH',
    'TODO': 'MEDIUM',
    'REFACTOR': 'MEDIUM',
    'OPTIMIZE': 'LOW',
    'NOTE': 'LOW',
}

# File extensions to scan
SCANNABLE_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.md', '.yaml', '.yml',
    '.json', '.html', '.css', '.scss', '.sh', '.bash',
}

# Directories to skip
SKIP_DIRECTORIES = {
    '.git', 'node_modules', '__pycache__', '.venv', 'logs',
    '.scannerwork', '.claude', '.next', 'dist', 'build',
    '.pytest_cache', 'coverage', 'htmlcov',
}

# Patterns to ignore (legitimate uses)
IGNORE_PATTERNS = [
    r'TODO_INVENTORY',  # Our own reports
    r'TODO_MANAGEMENT_GUIDE',  # Documentation
    r'scan_todos\.py',  # This script
    r'create_todo_issues\.py',  # Helper scripts
    r'update_todo_references\.py',  # Helper scripts
]


@dataclass
class TodoItem:
    """Represents a TODO marker found in the codebase."""
    marker: str
    severity: str
    file_path: Path
    line_number: int
    description: str
    issue_number: Optional[int]
    context: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'marker': self.marker,
            'severity': self.severity,
            'file_path': str(self.file_path),
            'line_number': self.line_number,
            'description': self.description,
            'issue_number': self.issue_number,
            'context': self.context,
        }


def get_tracked_files() -> List[Path]:
    """Get all git-tracked files in the repository."""
    try:
        result = subprocess.run(
            ['git', 'ls-files'],
            capture_output=True,
            text=True,
            check=True,
        )
        return [Path(f) for f in result.stdout.strip().split('\n') if f]
    except subprocess.CalledProcessError:
        return []


def is_scannable(path: Path) -> bool:
    """Check if file should be scanned for TODOs."""
    # Skip if in skip directory
    for skip_dir in SKIP_DIRECTORIES:
        if skip_dir in path.parts:
            return False

    # Skip if extension not scannable
    if path.suffix not in SCANNABLE_EXTENSIONS:
        return False

    # Skip if matches ignore pattern
    path_str = str(path)
    return all(not re.search(pattern, path_str) for pattern in IGNORE_PATTERNS)


def should_ignore_todo(item: TodoItem) -> bool:
    """Check if TODO should be ignored based on context."""
    # Ignore if already has issue reference
    if item.issue_number:
        return True

    # Ignore TODOs in documentation files (README, CONTRIBUTING)
    if item.file_path.name in {'README.md', 'CONTRIBUTING.md'}:
        return True

    # Ignore TODOs in example/template files
    return 'example' in str(item.file_path).lower() or 'template' in str(item.file_path).lower()


def get_line_number(content: str, match_start: int) -> int:
    """Calculate line number from match position."""
    return content[:match_start].count('\n') + 1


def extract_context(lines: List[str], line_num: int, context_lines: int = 2) -> str:
    """Extract surrounding context for a TODO."""
    start = max(0, line_num - context_lines - 1)
    end = min(len(lines), line_num + context_lines)
    context = lines[start:end]
    return ''.join(context)


def scan_file(path: Path) -> List[TodoItem]:
    """Scan a single file for TODO markers."""
    try:
        content = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return []

    lines = content.splitlines(keepends=True)
    todos = []

    # Pattern to match TODO markers with optional issue reference
    # Examples:
    #   # TODO: Fix this
    #   // TODO(#123): Fix this
    #   /* FIXME: Broken */
    #   <!-- TODO: Update -->
    pattern = re.compile(
        r'(?:^|\s)(?:#|//|/\*|<!--)\s*'
        r'(TODO|FIXME|HACK|XXX|OPTIMIZE|BUG|REFACTOR|NOTE)'
        r'(?:\(#(\d+)\))?'
        r'\s*:?\s*'
        r'(.+?)(?:\*/|-->|$)',
        re.IGNORECASE | re.MULTILINE
    )

    for match in pattern.finditer(content):
        marker = match.group(1).upper()
        issue_num = int(match.group(2)) if match.group(2) else None
        description = match.group(3).strip()
        line_num = get_line_number(content, match.start())
        context = extract_context(lines, line_num)

        severity = SEVERITY_MAP.get(marker, 'MEDIUM')

        todo = TodoItem(
            marker=marker,
            severity=severity,
            file_path=path,
            line_number=line_num,
            description=description,
            issue_number=issue_num,
            context=context,
        )

        todos.append(todo)

    return todos


def analyze_todos(todos: List[TodoItem]) -> Dict[str, Any]:
    """Generate statistics and analysis from TODO items."""
    if not todos:
        return {
            'total_count': 0,
            'by_severity': {},
            'by_marker': {},
            'by_directory': {},
            'with_issues': 0,
            'without_issues': 0,
            'compliance_rate': 100.0,
        }

    return {
        'total_count': len(todos),
        'by_severity': dict(Counter(t.severity for t in todos)),
        'by_marker': dict(Counter(t.marker for t in todos)),
        'by_directory': dict(Counter(str(t.file_path.parent) for t in todos)),
        'with_issues': sum(1 for t in todos if t.issue_number),
        'without_issues': sum(1 for t in todos if not t.issue_number),
        'compliance_rate': (sum(1 for t in todos if t.issue_number) / len(todos) * 100) if todos else 100.0,
    }


def generate_markdown_report(todos: List[TodoItem], stats: Dict[str, Any]) -> str:
    """Generate markdown format report."""
    report = []
    report.append("# TODO Inventory Report")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    report.append("## Summary Statistics")
    report.append(f"- Total TODOs: {stats['total_count']}")
    report.append(f"- With Issue References: {stats['with_issues']} ({stats['compliance_rate']:.1f}%)")
    report.append(f"- Without Issue References: {stats['without_issues']} ({100 - stats['compliance_rate']:.1f}%)")
    report.append(f"- Compliance Rate: {stats['compliance_rate']:.1f}%\n")

    report.append("## By Severity")
    for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        count = stats['by_severity'].get(severity, 0)
        report.append(f"- {severity}: {count}")
    report.append("")

    report.append("## By Marker Type")
    for marker, count in sorted(stats['by_marker'].items(), key=lambda x: x[1], reverse=True):
        report.append(f"- {marker}: {count}")
    report.append("")

    report.append("## By Directory (Top 10)")
    top_dirs = sorted(stats['by_directory'].items(), key=lambda x: x[1], reverse=True)[:10]
    for directory, count in top_dirs:
        report.append(f"- {directory}: {count}")
    report.append("")

    # Group by severity
    for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        severity_todos = [t for t in todos if t.severity == severity]
        if not severity_todos:
            continue

        report.append(f"## {severity} Items ({len(severity_todos)})\n")

        for i, todo in enumerate(severity_todos[:50], 1):  # Limit to 50 per severity
            compliance = "✅" if todo.issue_number else "❌"
            issue_ref = f"(#{todo.issue_number})" if todo.issue_number else "(no issue)"
            report.append(f"{i}. {compliance} `{todo.file_path}:{todo.line_number}` - {todo.marker}{issue_ref}: {todo.description[:80]}")

        if len(severity_todos) > 50:
            report.append(f"\n*... and {len(severity_todos) - 50} more {severity} items*")
        report.append("")

    report.append("## Recommendations")
    critical_count = stats['by_severity'].get('CRITICAL', 0)
    high_count = stats['by_severity'].get('HIGH', 0)

    if critical_count > 0:
        report.append(f"1. 🚨 Create GitHub issues for {critical_count} CRITICAL items immediately")
    if high_count > 0:
        report.append(f"2. ⚠️ Create GitHub issues for {high_count} HIGH priority items")
    if stats['without_issues'] > 0:
        report.append(f"3. 📝 Update {stats['without_issues']} non-compliant TODOs to reference issues")
    report.append("4. 🔄 Establish quarterly TODO review process")
    report.append("5. 📊 Monitor compliance rate in CI/CD")

    return '\n'.join(report)


def generate_json_report(todos: List[TodoItem], stats: Dict[str, Any]) -> str:
    """Generate JSON format report."""
    return json.dumps({
        'generated': datetime.now().isoformat(),
        'statistics': stats,
        'todos': [t.to_dict() for t in todos],
    }, indent=2)


def generate_csv_report(todos: List[TodoItem]) -> str:
    """Generate CSV format report."""
    import io
    output = io.StringIO()

    if not todos:
        return "No TODOs found"

    writer = csv.DictWriter(output, fieldnames=[
        'severity', 'marker', 'file_path', 'line_number',
        'description', 'issue_number', 'compliant'
    ])
    writer.writeheader()

    for todo in todos:
        writer.writerow({
            'severity': todo.severity,
            'marker': todo.marker,
            'file_path': str(todo.file_path),
            'line_number': todo.line_number,
            'description': todo.description,
            'issue_number': todo.issue_number or '',
            'compliant': 'Yes' if todo.issue_number else 'No',
        })

    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description='Scan for TODO markers')
    parser.add_argument('--format', choices=['markdown', 'json', 'csv'], default='markdown',
                        help='Output format')
    parser.add_argument('--output', type=Path, help='Output file path')
    parser.add_argument('--enforce', action='store_true',
                        help='Fail if non-compliant TODOs found')
    parser.add_argument('--severity', action='append', choices=['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
                        help='Filter by severity (can be specified multiple times)')
    parser.add_argument('--stats-only', action='store_true',
                        help='Show statistics only')
    args = parser.parse_args()

    # Scan all tracked files
    todos = []
    for file_path in get_tracked_files():
        if is_scannable(file_path):
            todos.extend(scan_file(file_path))

    # Filter by severity if specified
    if args.severity:
        todos = [t for t in todos if t.severity in args.severity]

    # Analyze
    stats = analyze_todos(todos)

    # Stats only mode
    if args.stats_only:
        print(f"Total TODOs: {stats['total_count']}")
        print(f"Compliance Rate: {stats['compliance_rate']:.1f}%")
        print(f"With Issues: {stats['with_issues']}")
        print(f"Without Issues: {stats['without_issues']}")
        print("\nBy Severity:")
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            count = stats['by_severity'].get(severity, 0)
            print(f"  {severity}: {count}")
        return

    # Generate report
    if args.format == 'markdown':
        report = generate_markdown_report(todos, stats)
    elif args.format == 'json':
        report = generate_json_report(todos, stats)
    else:  # csv
        report = generate_csv_report(todos)

    # Output
    if args.output:
        args.output.write_text(report)
        print(f"Report written to {args.output}")
    else:
        print(report)

    # Enforce policy
    if args.enforce:
        non_compliant = [t for t in todos if not t.issue_number and t.severity in ['CRITICAL', 'HIGH']]
        if non_compliant:
            print(f"\n❌ Found {len(non_compliant)} non-compliant TODOs (missing issue references)")
            print("\nShowing first 10 violations:")
            for todo in non_compliant[:10]:
                print(f"  {todo.file_path}:{todo.line_number} - {todo.marker}: {todo.description[:60]}")
            if len(non_compliant) > 10:
                print(f"  ... and {len(non_compliant) - 10} more")
            print("\n⚠️ Policy: CRITICAL and HIGH severity TODOs must reference a GitHub issue.")
            print("📝 Format: TODO(#123): Description")
            print("📖 See CONTRIBUTING.md for details")
            raise SystemExit(1)


if __name__ == '__main__':
    main()
