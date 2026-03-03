#!/usr/bin/env python3
"""
TODO Reference Updater

Updates TODO comments in source files to include GitHub issue references.

Usage:
    python scripts/ci/update_todo_references.py --mapping issues.json
    python scripts/ci/update_todo_references.py --interactive
    python scripts/ci/update_todo_references.py --file path/to/file.py --line 123 --issue 456
"""

import re
import json
import argparse
from pathlib import Path
from typing import Dict, Tuple


def update_todo_in_file(file_path: Path, line_number: int, issue_number: int) -> bool:
    """
    Update a TODO comment to include issue reference.

    Args:
        file_path: Path to the file
        line_number: Line number (1-indexed)
        issue_number: GitHub issue number

    Returns:
        True if update successful, False otherwise
    """
    try:
        lines = file_path.read_text(encoding='utf-8').splitlines(keepends=True)
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error reading {file_path}: {e}")
        return False

    if line_number > len(lines):
        print(f"Error: Line {line_number} exceeds file length ({len(lines)} lines)")
        return False

    line = lines[line_number - 1]

    # Detect comment style and update accordingly
    patterns = [
        # Python style: # TODO: ...
        (r'(#\s*)(TODO|FIXME|HACK|XXX|OPTIMIZE|BUG|REFACTOR|NOTE)(\s*:?\s*)',
         r'\1\2(#{issue})\3'),
        # JavaScript/TypeScript style: // TODO: ...
        (r'(//\s*)(TODO|FIXME|HACK|XXX|OPTIMIZE|BUG|REFACTOR|NOTE)(\s*:?\s*)',
         r'\1\2(#{issue})\3'),
        # Multi-line comment style: /* TODO: ...
        (r'(/\*\s*)(TODO|FIXME|HACK|XXX|OPTIMIZE|BUG|REFACTOR|NOTE)(\s*:?\s*)',
         r'\1\2(#{issue})\3'),
        # HTML/Markdown comment style: <!-- TODO: ...
        (r'(<!--\s*)(TODO|FIXME|HACK|XXX|OPTIMIZE|BUG|REFACTOR|NOTE)(\s*:?\s*)',
         r'\1\2(#{issue})\3'),
    ]

    updated = line
    for pattern, replacement in patterns:
        replacement_str = replacement.replace('{issue}', str(issue_number))
        updated = re.sub(pattern, replacement_str, line, flags=re.IGNORECASE)
        if updated != line:
            break

    if updated == line:
        print(f"Warning: Could not find TODO marker pattern in line: {line.strip()}")
        return False

    lines[line_number - 1] = updated
    try:
        file_path.write_text(''.join(lines), encoding='utf-8')
        return True
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error writing {file_path}: {e}")
        return False


def batch_update_todos(mapping: Dict[str, int], dry_run: bool = False) -> Tuple[int, int]:
    """
    Update multiple TODOs from a mapping file.

    Args:
        mapping: Dictionary mapping "file:line" to issue number
        dry_run: If True, show what would be updated without updating

    Returns:
        Tuple of (successful_updates, failed_updates)
    """
    successful = 0
    failed = 0

    for location, issue_num in mapping.items():
        try:
            file_path_str, line_num_str = location.rsplit(':', 1)
            file_path = Path(file_path_str)
            line_num = int(line_num_str)
        except ValueError:
            print(f"  ❌ Invalid location format: {location}")
            failed += 1
            continue

        if not file_path.exists():
            print(f"  ❌ File not found: {file_path}")
            failed += 1
            continue

        if dry_run:
            print(f"  🔍 Would update: {file_path}:{line_num} → #{issue_num}")
            successful += 1
        elif update_todo_in_file(file_path, line_num, issue_num):
            print(f"  ✅ Updated: {file_path}:{line_num} → #{issue_num}")
            successful += 1
        else:
            print(f"  ❌ Failed: {file_path}:{line_num}")
            failed += 1

    return successful, failed


def interactive_update():
    """Interactively update TODOs by prompting for each one."""
    from scan_todos import scan_file, get_tracked_files, is_scannable

    print("🔍 Scanning codebase for TODOs...\n")
    todos = []
    for file_path in get_tracked_files():
        if is_scannable(file_path):
            todos.extend(scan_file(file_path))

    # Filter out TODOs that already have issue references
    todos = [t for t in todos if not t.issue_number]

    if not todos:
        print("✅ No TODOs found without issue references")
        return

    print(f"Found {len(todos)} TODOs without issue references\n")

    updated = 0
    skipped = 0
    failed = 0

    for i, todo in enumerate(todos, 1):
        print(f"\n[{i}/{len(todos)}] {todo.file_path}:{todo.line_number}")
        print(f"  {todo.marker}: {todo.description}")
        print(f"  Severity: {todo.severity}")

        # Show context
        if todo.context:
            print("\n  Context:")
            for line in todo.context.strip().split('\n'):
                print(f"    {line}")

        response = input("\n  Enter issue number (or 's' to skip, 'q' to quit): ").strip()

        if response.lower() == 'q':
            print("\n👋 Quitting interactive mode")
            break
        elif response.lower() == 's':
            print("  ⏭️  Skipped")
            skipped += 1
            continue
        elif response.isdigit():
            issue_num = int(response)
            if update_todo_in_file(todo.file_path, todo.line_number, issue_num):
                print(f"  ✅ Updated with issue #{issue_num}")
                updated += 1
            else:
                print("  ❌ Failed to update")
                failed += 1
        else:
            print("  ⚠️  Invalid input, skipping")
            skipped += 1

    print("\n📊 Summary:")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")


def preview_update(file_path: Path, line_number: int, issue_number: int):
    """
    Show what the update would look like without making changes.

    Args:
        file_path: Path to the file
        line_number: Line number (1-indexed)
        issue_number: GitHub issue number
    """
    try:
        lines = file_path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error reading {file_path}: {e}")
        return

    if line_number > len(lines):
        print(f"Error: Line {line_number} exceeds file length ({len(lines)} lines)")
        return

    # Show context
    start = max(0, line_number - 3)
    end = min(len(lines), line_number + 2)

    print("\nCurrent:")
    for i in range(start, end):
        marker = ">>>" if i == line_number - 1 else "   "
        print(f"{marker} {i + 1:4d} | {lines[i]}")

    # Simulate update
    line = lines[line_number - 1]
    patterns = [
        (r'(#\s*)(TODO|FIXME|HACK|XXX|OPTIMIZE|BUG|REFACTOR|NOTE)(\s*:?\s*)',
         r'\1\2(#{issue})\3'),
        (r'(//\s*)(TODO|FIXME|HACK|XXX|OPTIMIZE|BUG|REFACTOR|NOTE)(\s*:?\s*)',
         r'\1\2(#{issue})\3'),
        (r'(/\*\s*)(TODO|FIXME|HACK|XXX|OPTIMIZE|BUG|REFACTOR|NOTE)(\s*:?\s*)',
         r'\1\2(#{issue})\3'),
        (r'(<!--\s*)(TODO|FIXME|HACK|XXX|OPTIMIZE|BUG|REFACTOR|NOTE)(\s*:?\s*)',
         r'\1\2(#{issue})\3'),
    ]

    updated = line
    for pattern, replacement in patterns:
        replacement_str = replacement.replace('{issue}', str(issue_number))
        updated = re.sub(pattern, replacement_str, line, flags=re.IGNORECASE)
        if updated != line:
            break

    print("\nAfter update:")
    for i in range(start, end):
        marker = ">>>" if i == line_number - 1 else "   "
        display_line = updated if i == line_number - 1 else lines[i]
        print(f"{marker} {i + 1:4d} | {display_line}")


def main():
    parser = argparse.ArgumentParser(description='Update TODO comments with issue references')
    parser.add_argument('--mapping', type=Path,
                        help='JSON file mapping locations to issue numbers')
    parser.add_argument('--interactive', action='store_true',
                        help='Interactively update TODOs')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be updated without updating')
    parser.add_argument('--file', type=Path,
                        help='Update specific file only')
    parser.add_argument('--line', type=int,
                        help='Update specific line (requires --file)')
    parser.add_argument('--issue', type=int,
                        help='Issue number (requires --file and --line)')
    parser.add_argument('--preview', action='store_true',
                        help='Preview the update (requires --file, --line, --issue)')
    args = parser.parse_args()

    if args.interactive:
        interactive_update()
    elif args.mapping:
        if not args.mapping.exists():
            print(f"❌ Error: Mapping file not found: {args.mapping}")
            return

        try:
            mapping = json.loads(args.mapping.read_text())
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in mapping file: {e}")
            return

        print(f"📝 Updating TODOs from {args.mapping}...\n")
        successful, failed = batch_update_todos(mapping, args.dry_run)

        print("\n📊 Summary:")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")

        if args.dry_run:
            print("\n💡 This was a dry run. No files were modified.")
            print("   Remove --dry-run to update for real")
    elif args.file and args.line and args.issue:
        if not args.file.exists():
            print(f"❌ Error: File not found: {args.file}")
            return

        if args.preview:
            preview_update(args.file, args.line, args.issue)
        elif args.dry_run:
            print(f"🔍 Would update: {args.file}:{args.line} → #{args.issue}")
            preview_update(args.file, args.line, args.issue)
        elif update_todo_in_file(args.file, args.line, args.issue):
            print(f"✅ Updated: {args.file}:{args.line} → #{args.issue}")
        else:
            print(f"❌ Failed to update {args.file}:{args.line}")
    else:
        parser.error("Must specify --mapping, --interactive, or --file/--line/--issue")


if __name__ == "__main__":
    main()
