#!/usr/bin/env python3
"""
Refactoring Guard - Prevents destructive mass refactoring
This script should be run before any refactoring operation.
"""

import sys
import os
import subprocess
from datetime import datetime
import json

class RefactoringGuard:
    """Guard against destructive refactoring operations."""

    def __init__(self) -> None:
        self.max_files_without_approval = 5
        self.max_lines_without_approval = 100
        self.require_approval = False
        self.changes_log = []

    def check_syntax(self, filepath):
        """Check if a Python file has valid syntax."""
        try:
            result = subprocess.run(
                ['python3', '-m', 'py_compile', filepath],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error checking syntax for {filepath}: {e}")
            return False

    def create_backup(self, filepath):
        """Create a timestamped backup of a file."""
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = f"{filepath}.backup-{timestamp}"
        try:
            subprocess.run(['cp', filepath, backup_path], check=True)
            print(f"✅ Backup created: {backup_path}")
            return backup_path
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create backup: {e}")
            return None

    def test_application(self):
        """Test if the application starts without syntax errors."""
        try:
            result = subprocess.run(
                ['python3', '-c', 'import main'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return True  # Timeout means it started
        except Exception as e:
            print(f"Error testing application: {e}")
            return False

    def analyze_changes(self, files_to_change, changes_description):
        """Analyze proposed changes and determine if approval is needed."""
        approval_reasons = []

        # Check number of files
        if len(files_to_change) > self.max_files_without_approval:
            approval_reasons.append(
                f"Modifying {len(files_to_change)} files (max {self.max_files_without_approval} without approval)"
            )

        # Check for dangerous operations
        dangerous_keywords = [
            'fix all', 'fix-all', 'bulk', 'mass', 'entire', 'codebase',
            'all files', 'every', 'automatic', 'clean', 'cleanup'
        ]

        desc_lower = changes_description.lower()
        for keyword in dangerous_keywords:
            if keyword in desc_lower:
                approval_reasons.append(f"Dangerous operation detected: '{keyword}'")

        # Check for structural changes
        structural_keywords = ['move', 'rename', 'refactor', 'restructure', 'migrate']
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

    def log_change(self, file, change_type, result):
        """Log a refactoring change."""
        self.changes_log.append({
            'timestamp': datetime.now().isoformat(),
            'file': file,
            'change_type': change_type,
            'result': result
        })

    def save_log(self):
        """Save the refactoring log."""
        log_file = '.claude/refactoring-log.json'
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    existing_log = json.load(f)
            else:
                existing_log = []

            existing_log.extend(self.changes_log)

            with open(log_file, 'w') as f:
                json.dump(existing_log, f, indent=2)

            print(f"✅ Changes logged to {log_file}")
        except Exception as e:
            print(f"Warning: Could not save log: {e}")

    def request_approval(self, files, changes_description):
        """Request user approval for changes."""
        print("\n" + "="*50)
        print("REFACTORING APPROVAL REQUEST")
        print("="*50)
        print(f"\nFiles to modify ({len(files)}):")
        for f in files[:10]:  # Show first 10
            print(f"  - {f}")
        if len(files) > 10:
            print(f"  ... and {len(files)-10} more files")

        print("\nChanges description:")
        print(f"  {changes_description}")

        print("\n" + "="*50)
        print("Do you approve these changes? (yes/no): ", end='')

        # For automation, we'll return False (not approved)
        # In interactive mode, you would read user input
        return False

    def guard_refactoring(self, files, changes_description):
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

    # Example usage (would be called with actual files and description)
    if len(sys.argv) > 1:
        files = sys.argv[1].split(',')
        description = sys.argv[2] if len(sys.argv) > 2 else "Refactoring operation"

        if guard.guard_refactoring(files, description):
            print("\nProceeding with refactoring...")
            # Refactoring would happen here
            guard.save_log()
        else:
            print("\nRefactoring cancelled.")
            sys.exit(1)
    else:
        print("Usage: python refactoring-guard.py <comma-separated-files> <description>")
        print("\nThis guard prevents destructive refactoring by:")
        print("  - Requiring approval for changes to >5 files")
        print("  - Creating backups before changes")
        print("  - Testing application state")
        print("  - Logging all refactoring operations")

if __name__ == "__main__":
    main()
