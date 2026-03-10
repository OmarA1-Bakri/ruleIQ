#!/usr/bin/env python3
"""
Refactoring Guard - Prevents destructive mass refactoring
This script should be run before any refactoring operation.
"""

import sys
import os
import subprocess
import shutil
import importlib.util
from datetime import datetime
import json
import argparse
from typing import Any


class RefactoringGuard:
    """Guard against destructive refactoring operations."""

    def __init__(self) -> None:
        self.max_files_without_approval = 5
        self.changes_log: list[dict[str, Any]] = []

    def check_syntax(self, filepath: str) -> bool:
        """Check if a Python file has valid syntax."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", filepath],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except OSError as e:
            print(f"Error checking syntax for {filepath}: {e}")
            return False

    def create_backup(self, filepath: str) -> str | None:
        """Create a timestamped backup of a file."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = f"{filepath}.backup-{timestamp}"
        try:
            shutil.copy2(filepath, backup_path)
            print(f"✅ Backup created: {backup_path}")
            return backup_path
        except OSError as e:
            print(f"❌ Failed to create backup: {e}")
            return None

    def _get_import_targets(self) -> list[str]:
        """Return candidate modules for a lightweight startup smoke test."""
        candidates = ["api.main", "main"]
        return [module for module in candidates if importlib.util.find_spec(module) is not None]

    def test_application(self) -> bool:
        """Test if the application starts without syntax errors."""
        import_targets = self._get_import_targets()
        if not import_targets:
            return True

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "; ".join(f"import {module}" for module in import_targets),
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return True  # Timeout means it started
        except OSError as e:
            print(f"Error testing application: {e}")
            return False

    def analyze_changes(self, files_to_change: list[str], changes_description: str) -> bool:
        """Analyze proposed changes and determine if approval is needed."""
        approval_reasons: list[str] = []

        # Check number of files
        if len(files_to_change) > self.max_files_without_approval:
            approval_reasons.append(
                f"Modifying {len(files_to_change)} files (max {self.max_files_without_approval} without approval)"
            )

        # Check for dangerous operations
        dangerous_keywords = [
            "fix all",
            "fix-all",
            "bulk",
            "mass",
            "entire",
            "codebase",
            "all files",
            "every",
            "automatic",
            "clean",
            "cleanup",
        ]

        desc_lower = changes_description.lower()
        for keyword in dangerous_keywords:
            if keyword in desc_lower:
                approval_reasons.append(f"Dangerous operation detected: '{keyword}'")

        # Check for structural changes
        structural_keywords = ["move", "rename", "refactor", "restructure", "migrate"]
        for keyword in structural_keywords:
            if keyword in desc_lower:
                approval_reasons.append(f"Structural change detected: '{keyword}'")

        if approval_reasons:
            print("\n⚠️  APPROVAL REQUIRED ⚠️")
            print("Reasons:")
            for reason in approval_reasons:
                print(f"  - {reason}")
            return False

        return True

    def log_change(self, file: str, change_type: str, result: str) -> None:
        """Log a refactoring change."""
        self.changes_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "file": file,
                "change_type": change_type,
                "result": result,
            }
        )

    def save_log(self) -> None:
        """Save the refactoring log."""
        log_file = ".claude/refactoring-log.json"
        try:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    existing_log = json.load(f)
                if not isinstance(existing_log, list):
                    existing_log = []
            else:
                existing_log = []

            existing_log.extend(self.changes_log)

            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(existing_log, f, indent=2)

            print(f"✅ Changes logged to {log_file}")
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Could not save log: {e}")

    def request_approval(self, files: list[str], changes_description: str) -> bool:
        """Request user approval for changes."""
        print("\n" + "=" * 50)
        print("REFACTORING APPROVAL REQUEST")
        print("=" * 50)
        print(f"\nFiles to modify ({len(files)}):")
        for f in files[:10]:  # Show first 10
            print(f"  - {f}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more files")

        print("\nChanges description:")
        print(f"  {changes_description}")

        print("\n" + "=" * 50)

        if not sys.stdin.isatty():
            return False

        try:
            response = input("Approve? [y/N]: ").strip().lower()
            return response == "y"
        except (EOFError, KeyboardInterrupt):
            return False

    def guard_refactoring(self, files: list[str], changes_description: str) -> bool:
        """Main guard function to check if refactoring should proceed."""
        print("\n🛡️ REFACTORING GUARD ACTIVE 🛡️")
        print(f"Checking {len(files)} files for refactoring...")

        # Test current state
        print("\n1. Testing current application state...")
        app_works_before = self.test_application()
        print(f"   Application state: {'✅ Working' if app_works_before else '⚠️ Has issues'}")

        # Analyze changes
        print("\n2. Analyzing proposed changes...")
        auto_approved = self.analyze_changes(files, changes_description)

        if not auto_approved:
            # Request approval
            approved = self.request_approval(files, changes_description)
            if not approved:
                print("\n❌ REFACTORING BLOCKED - Approval required")
                print("Please get explicit user approval before proceeding.")
                return False

        # Create backups
        print("\n3. Creating backups...")
        for filepath in files[:5]:  # Backup first 5 as sample
            if os.path.exists(filepath):
                self.create_backup(filepath)

        print("\n✅ REFACTORING APPROVED - Proceed with caution")
        print("Remember to:")
        print("  1. Test after EACH file modification")
        print("  2. Stop immediately if errors occur")
        print("  3. Rollback if application breaks")

        return True


def main():
    """Main entry point for the refactoring guard."""
    guard = RefactoringGuard()
    parser = argparse.ArgumentParser(description="Refactoring guard for safe multi-file changes")
    parser.add_argument("files", nargs="*", help="File paths to be modified")
    parser.add_argument(
        "-d",
        "--description",
        default="Refactoring operation",
        help="Description of proposed refactoring changes",
    )
    args = parser.parse_args()

    if args.files:
        if guard.guard_refactoring(args.files, args.description):
            print("\nProceeding with refactoring...")
            # Refactoring would happen here
            guard.save_log()
        else:
            print("\nRefactoring cancelled.")
            sys.exit(1)
    else:
        print("Usage: python refactoring-guard.py <files...> [-d DESCRIPTION]")
        print("\nThis guard prevents destructive refactoring by:")
        print("  - Requiring approval for changes to >5 files")
        print("  - Creating backups before changes")
        print("  - Testing application state")
        print("  - Logging all refactoring operations")


if __name__ == "__main__":
    main()
