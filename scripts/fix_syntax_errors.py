#!/usr/bin/env python3
"""
Script to detect and fix common syntax errors in Python files.
Focuses on fixing missing newlines, removing stray XML tags, and validating syntax.
"""

import ast
import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Optional


class SyntaxFixer:
    """Handles detection and fixing of syntax errors in Python files."""

    def __init__(self, backup: bool = True, dry_run: bool = False) -> None:
        self.backup = backup
        self.dry_run = dry_run
        self.fixed_files = []
        self.error_files = []
        self.skipped_files = []

    def scan_directory(self, path: Path) -> List[Path]:
        """Scan directory for Python files."""
        python_files = []

        for root, dirs, files in os.walk(path):
            # Skip common directories we don't want to check
            dirs[:] = [
                d for d in dirs if d not in {".venv", "venv", "__pycache__", ".git", "node_modules"}
            ]

            for file in files:
                if file.endswith(".py"):
                    python_files.append(Path(root) / file)

        return python_files

    def check_file_syntax(self, filepath: Path) -> Tuple[bool, Optional[str]]:
        """Check if a Python file has valid syntax."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source)
            return True, None
        except SyntaxError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Error reading file: {e}"

    def fix_file_endings(self, filepath: Path) -> bool:
        """Fix common file ending issues."""
        try:
            with open(filepath, "rb") as f:
                content = f.read()

            # Convert to string for processing
            text = content.decode("utf-8")
            original_text = text

            # Remove common XML/HTML tags that shouldn't be in Python files
            patterns_to_remove = [
                r"</content>\s*$",
                r"</edit_file>\s*$",
                r"</file>\s*$",
                r"</code>\s*$",
            ]

            for pattern in patterns_to_remove:
                text = re.sub(pattern, "", text)

            # Ensure file ends with a newline
            if text and not text.endswith("\n"):
                text += "\n"

            # Check if we made any changes
            if text == original_text:
                return False

            # Create backup if requested
            if self.backup and not self.dry_run:
                backup_path = filepath.with_suffix(".py.bak")
                shutil.copy2(filepath, backup_path)

            # Write fixed content
            if not self.dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(text)

            return True

        except Exception as e:
            print(f"Error fixing {filepath}: {e}")
            return False

    def validate_imports(self, filepath: Path) -> List[str]:
        """Check for import issues in a file."""
        issues = []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Basic check - more sophisticated validation could be added
                        if alias.name.startswith("_"):
                            issues.append(
                                f"Line {node.lineno}: Importing private module {alias.name}"
                            )

                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("_"):
                        issues.append(
                            f"Line {node.lineno}: Importing from private module {node.module}"
                        )

        except Exception:
            pass  # If we can't parse, skip import validation

        return issues

    def fix_file(self, filepath: Path) -> Dict[str, any]:
        """Attempt to fix a single file."""
        result = {
            "file": str(filepath),
            "status": "unknown",
            "syntax_valid_before": False,
            "syntax_valid_after": False,
            "changes_made": False,
            "errors": [],
        }

        # Check initial syntax
        valid_before, error_before = self.check_file_syntax(filepath)
        result["syntax_valid_before"] = valid_before

        if not valid_before:
            result["errors"].append(f"Initial syntax error: {error_before}")

        # Try to fix file endings and common issues
        changes_made = self.fix_file_endings(filepath)
        result["changes_made"] = changes_made

        # Check syntax after fixes
        valid_after, error_after = self.check_file_syntax(filepath)
        result["syntax_valid_after"] = valid_after

        if not valid_after:
            result["errors"].append(f"Syntax error after fix: {error_after}")

        # Check imports
        import_issues = self.validate_imports(filepath)
        if import_issues:
            result["import_issues"] = import_issues

        # Determine final status
        if valid_before and not changes_made:
            result["status"] = "ok"
            self.skipped_files.append(filepath)
        elif not valid_before and valid_after:
            result["status"] = "fixed"
            self.fixed_files.append(filepath)
        elif valid_before and changes_made and valid_after:
            result["status"] = "cleaned"
            self.fixed_files.append(filepath)
        else:
            result["status"] = "error"
            self.error_files.append(filepath)

        return result

    def process_files(self, files: List[Path]) -> List[Dict]:
        """Process multiple files."""
        results = []

        for i, filepath in enumerate(files, 1):
            print(f"Processing ({i}/{len(files)}): {filepath}")
            result = self.fix_file(filepath)
            results.append(result)

            if result["status"] == "fixed":
                print("  ✓ Fixed syntax errors")
            elif result["status"] == "cleaned":
                print("  ✓ Cleaned file endings")
            elif result["status"] == "error":
                print("  ✗ Could not fix errors")
            else:
                print("  - No changes needed")

        return results

    def print_summary(self):
        """Print a summary of the fixes."""
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Files fixed: {len(self.fixed_files)}")
        print(f"Files with errors: {len(self.error_files)}")
        print(f"Files skipped (already valid): {len(self.skipped_files)}")

        if self.fixed_files:
            print("\nFixed files:")
            for f in self.fixed_files[:10]:
                print(f"  - {f}")
            if len(self.fixed_files) > 10:
                print(f"  ... and {len(self.fixed_files) - 10} more")

        if self.error_files:
            print("\nFiles with unresolved errors:")
            for f in self.error_files:
                print(f"  - {f}")


def main():
    parser = argparse.ArgumentParser(description="Fix syntax errors in Python files")
    parser.add_argument(
        "path", nargs="?", default=".", help="Path to scan (default: current directory)"
    )
    parser.add_argument("--no-backup", action="store_true", help="Do not create backup files")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be fixed without making changes"
    )
    parser.add_argument("--file", help="Fix a single file instead of scanning directory")
    parser.add_argument(
        "--ci", action="store_true", help="CI mode - exit with error if issues found"
    )

    args = parser.parse_args()

    fixer = SyntaxFixer(backup=not args.no_backup, dry_run=args.dry_run)

    if args.dry_run:
        print("DRY RUN MODE - No changes will be made\n")

    if args.file:
        # Process single file
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"Error: File {filepath} not found")
            sys.exit(1)

        fixer.process_files([filepath])
    else:
        # Process directory
        path = Path(args.path)
        if not path.exists():
            print(f"Error: Path {path} not found")
            sys.exit(1)

        print(f"Scanning {path} for Python files...")
        files = fixer.scan_directory(path)
        print(f"Found {len(files)} Python files\n")

        fixer.process_files(files)

    fixer.print_summary()

    # Exit code for CI
    if args.ci:
        if fixer.error_files:
            print("\nCI Mode: Errors found that could not be fixed")
            sys.exit(1)
        elif fixer.fixed_files and not args.dry_run:
            print("\nCI Mode: Files were fixed - please review changes")
            sys.exit(0)
        else:
            print("\nCI Mode: All files are valid")
            sys.exit(0)


if __name__ == "__main__":
    main()
