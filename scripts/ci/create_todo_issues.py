#!/usr/bin/env python3
"""
GitHub Issue Creator for TODOs

Automatically creates GitHub issues for TODOs without issue references.

Usage:
    python scripts/ci/create_todo_issues.py --token $GITHUB_TOKEN --repo owner/repo --dry-run
    python scripts/ci/create_todo_issues.py --token $GITHUB_TOKEN --repo owner/repo --severity CRITICAL
    python scripts/ci/create_todo_issues.py --token $GITHUB_TOKEN --repo owner/repo --batch-similar
"""

import os
import sys
import json
import requests
import argparse
from pathlib import Path
from scan_todos import TodoItem, scan_file, get_tracked_files, is_scannable


class GitHubIssueCreator:
    """Handles GitHub API interactions for issue creation."""

    def __init__(self, token: str, repo: str) -> None:
        """
        Initialize GitHub API client.

        Args:
            token: GitHub personal access token
            repo: Repository in format "owner/repo"
        """
        self.token = token
        self.repo = repo
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def create_issue(self, title: str, body: str, labels: list[str]) -> int:
        """
        Create a GitHub issue.

        Args:
            title: Issue title
            body: Issue body (markdown)
            labels: List of label names

        Returns:
            Issue number

        Raises:
            requests.HTTPError: If API call fails
        """
        url = f"{self.api_base}/repos/{self.repo}/issues"
        data = {"title": title, "body": body, "labels": labels}
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()["number"]

    def search_existing_issue(self, title: str) -> int | None:
        """
        Search for existing issue with similar title to avoid duplicates.

        Args:
            title: Issue title to search for

        Returns:
            Issue number if found, None otherwise
        """
        url = f"{self.api_base}/search/issues"
        # Truncate title for search to avoid query length limits
        search_title = title[:100]
        query = f"repo:{self.repo} is:issue is:open in:title {search_title}"
        params = {"q": query}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            items = response.json().get("items", [])
            return items[0]["number"] if items else None
        except requests.HTTPError:
            return None


def group_similar_todos(todos: list[TodoItem]) -> dict[str, list[TodoItem]]:
    """
    Group similar TODOs to create batch issues.

    Args:
        todos: List of TODO items

    Returns:
        Dictionary mapping group key to list of TODOs
    """
    groups = {}

    for todo in todos:
        # Normalize description
        normalized = todo.description.lower().strip()

        # Check for common patterns
        if "replace with proper logging" in normalized or "add logging" in normalized:
            key = "logging-infrastructure"
        elif "implementation pending" in normalized or "not implemented" in normalized:
            key = f"implement-{todo.file_path.stem}"
        elif "test" in normalized and ("add" in normalized or "write" in normalized):
            key = f"tests-{todo.file_path.stem}"
        elif "refactor" in normalized or "clean up" in normalized:
            key = f"refactor-{todo.file_path.stem}"
        else:
            # Use first 50 chars as key for unique TODOs
            key = normalized[:50]

        if key not in groups:
            groups[key] = []
        groups[key].append(todo)

    return groups


def generate_issue_body(todos: list[TodoItem]) -> str:
    """
    Generate issue body from TODO items.

    Args:
        todos: List of TODO items (1 or more)

    Returns:
        Markdown-formatted issue body
    """
    if len(todos) == 1:
        todo = todos[0]
        return f"""## Description
{todo.description}

## Location
- **File**: `{todo.file_path}`
- **Line**: {todo.line_number}

## Context
```python
{todo.context}
```

## Details
- **Severity**: {todo.severity}
- **Marker**: {todo.marker}

---
*Auto-generated from TODO comment*
"""
    else:
        # Multiple TODOs in one issue
        body = f"""## Description
This issue tracks {len(todos)} related TODO items that should be addressed together.

## Locations
"""
        for i, todo in enumerate(todos, 1):
            body += f"{i}. `{todo.file_path}:{todo.line_number}` - {todo.description}\n"

        body += f"""
## Severity
{todos[0].severity} (all items have similar severity)

---
*Auto-generated from {len(todos)} TODO comments*
"""
        return body


def get_labels_for_todo(todo: TodoItem) -> list[str]:
    """
    Determine appropriate labels for the issue.

    Args:
        todo: TODO item

    Returns:
        List of label names
    """
    labels = ["technical-debt", "todo"]

    # Severity label
    if todo.severity == "CRITICAL":
        labels.append("priority: critical")
    elif todo.severity == "HIGH":
        labels.append("priority: high")
    elif todo.severity == "MEDIUM":
        labels.append("priority: medium")
    else:
        labels.append("priority: low")

    # Marker-specific labels
    if todo.marker in {"FIXME", "BUG"}:
        labels.append("bug")
    elif todo.marker == "HACK":
        labels.append("refactoring")
    elif todo.marker == "OPTIMIZE":
        labels.append("performance")
    elif todo.marker == "REFACTOR":
        labels.append("refactoring")

    # Area labels based on file path
    path_str = str(todo.file_path).lower()
    if "frontend" in path_str:
        labels.append("frontend")
    elif "api" in path_str or "routers" in path_str or "services" in path_str:
        labels.append("backend")
    elif "tests" in path_str or "test_" in path_str:
        labels.append("testing")
    elif "docs" in path_str:
        labels.append("documentation")

    return labels


def main():
    parser = argparse.ArgumentParser(description="Create GitHub issues for TODOs")
    parser.add_argument(
        "--token", help="GitHub personal access token (or set GITHUB_TOKEN env var)"
    )
    parser.add_argument("--repo", required=True, help="Repository in format owner/repo")
    parser.add_argument(
        "--severity",
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        help="Only create issues for this severity",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be created without creating"
    )
    parser.add_argument(
        "--batch-similar", action="store_true", help="Group similar TODOs into single issues"
    )
    parser.add_argument(
        "--max-issues", type=int, default=50, help="Maximum number of issues to create in one run"
    )
    args = parser.parse_args()

    # Get GitHub token
    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print(
            "❌ Error: GitHub token required. Use --token or set GITHUB_TOKEN environment variable"
        )
        sys.exit(1)

    # Scan for TODOs
    print("🔍 Scanning codebase for TODOs...")
    todos = []
    for file_path in get_tracked_files():
        if is_scannable(file_path):
            todos.extend(scan_file(file_path))

    print(f"Found {len(todos)} total TODOs")

    # Filter by severity if specified
    if args.severity:
        todos = [t for t in todos if t.severity == args.severity]
        print(f"Filtered to {len(todos)} TODOs with severity: {args.severity}")

    # Filter out TODOs that already have issue references
    todos = [t for t in todos if not t.issue_number]
    print(f"Found {len(todos)} TODOs without issue references")

    if not todos:
        print("✅ No TODOs need issues created")
        return

    # Group if requested
    if args.batch_similar:
        groups = group_similar_todos(todos)
        print(f"📦 Grouped into {len(groups)} potential issue(s)")
    else:
        groups = {f"todo-{i}": [todo] for i, todo in enumerate(todos)}

    # Limit number of issues
    if len(groups) > args.max_issues:
        print(f"⚠️ Warning: Would create {len(groups)} issues, limiting to {args.max_issues}")
        groups = dict(list(groups.items())[: args.max_issues])

    # Create issues
    creator = GitHubIssueCreator(token, args.repo)
    created_issues = []
    skipped = 0

    print(f"\n{'🔍 DRY RUN - ' if args.dry_run else ''}Creating issues...\n")

    for group_key, group_todos in groups.items():
        # Generate title
        if len(group_todos) == 1:
            todo = group_todos[0]
            title = f"{todo.marker}: {todo.description[:80]}"
        else:
            # Use first TODO's description as base
            title = f"[Batch] {len(group_todos)} TODOs: {group_key}"

        # Truncate title if too long
        if len(title) > 100:
            title = title[:97] + "..."

        # Check for existing issue
        if not args.dry_run:
            existing = creator.search_existing_issue(title)
            if existing:
                print(f"  ⏭️  Skipping (exists): #{existing} - {title}")
                skipped += 1
                continue

        # Generate body and labels
        body = generate_issue_body(group_todos)
        labels = get_labels_for_todo(group_todos[0])

        if args.dry_run:
            print(f"  🔍 Would create: {title}")
            print(f"     Labels: {', '.join(labels)}")
            print(f"     TODOs: {len(group_todos)}")
            created_issues.append((None, group_todos))
        else:
            try:
                issue_number = creator.create_issue(title, body, labels)
                created_issues.append((issue_number, group_todos))
                print(f"  ✅ Created: #{issue_number} - {title}")
            except requests.HTTPError as e:
                print(f"  ❌ Failed: {title}")
                print(f"     Error: {e}")
                continue

    # Summary
    print("\n📊 Summary:")
    print(f"  Total TODOs processed: {len(todos)}")
    print(f"  Issues created: {len(created_issues)}")
    if skipped > 0:
        print(f"  Issues skipped (already exist): {skipped}")

    # Generate mapping file for update script
    if created_issues and not args.dry_run:
        mapping = {}
        for issue_num, group_todos in created_issues:
            if issue_num:  # Skip if dry run
                for todo in group_todos:
                    key = f"{todo.file_path}:{todo.line_number}"
                    mapping[key] = issue_num

        mapping_file = Path("issues.json")
        mapping_file.write_text(json.dumps(mapping, indent=2))
        print(f"\n💾 Saved issue mapping to {mapping_file}")
        print("\n📝 Next step: Update TODO comments with issue references")
        print("   Run: python scripts/ci/update_todo_references.py --mapping issues.json")
    elif created_issues and args.dry_run:
        print("\n💡 This was a dry run. No issues were created.")
        print("   Remove --dry-run to create issues for real")


if __name__ == "__main__":
    main()
