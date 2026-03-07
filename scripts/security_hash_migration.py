#!/usr/bin/env python3
"""
Security Hash Migration Script

Manages the transition from MD5 to SHA-256 hashing throughout the RuleIQ codebase.
This script validates the migration, provides rollback capabilities, and ensures
no regression to insecure hashing.
"""

import os
import re
import sys
import json
import hashlib
import argparse
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import logging


logger = logging.getLogger(__name__)
# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.logging_config import get_logger

logger = get_logger(__name__)


class HashMigrationValidator:
    """Validates and manages the MD5 to SHA-256 migration."""

    MD5_PATTERNS = [
        r"hashlib\.md5\(",
        r"\.md5\(",
        r"MD5\(",
        r"import\s+md5",
        r"from\s+hashlib\s+import\s+md5",
    ]

    SHA256_PATTERNS = [
        r"hashlib\.sha256\(",
        r"\.sha256\(",
        r"SHA256\(",
    ]

    EXCLUDED_PATHS = [
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        "htmlcov",
        "migrations",
    ]

    def __init__(self, project_root: Path) -> None:
        """Initialize the migration validator."""
        self.project_root = project_root
        self.findings: List[Dict] = []
        self.migration_report: Dict = {
            "timestamp": datetime.utcnow().isoformat(),
            "files_scanned": 0,
            "md5_found": [],
            "sha256_found": [],
            "migration_needed": [],
            "migration_complete": [],
            "errors": [],
        }

    def scan_codebase(self) -> Dict:
        """Scan the entire codebase for hash usage."""
        logger.info("Starting codebase scan for hash usage...")

        for root, dirs, files in os.walk(self.project_root):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_PATHS]

            for file in files:
                if file.endswith((".py", ".js", ".ts", ".jsx", ".tsx")):
                    file_path = Path(root) / file
                    self._scan_file(file_path)

        self._generate_summary()
        return self.migration_report

    def _scan_file(self, file_path: Path) -> None:
        """Scan a single file for hash usage."""
        self.migration_report["files_scanned"] += 1

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")

            md5_found = False
            sha256_found = False
            findings = []

            for line_num, line in enumerate(lines, 1):
                # Check for MD5 usage
                for pattern in self.MD5_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        md5_found = True
                        findings.append({"line": line_num, "content": line.strip(), "type": "MD5"})

                # Check for SHA256 usage
                for pattern in self.SHA256_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        sha256_found = True
                        findings.append(
                            {"line": line_num, "content": line.strip(), "type": "SHA256"}
                        )

            # Categorize the file
            relative_path = str(file_path.relative_to(self.project_root))

            if md5_found and not sha256_found:
                self.migration_report["migration_needed"].append(
                    {"file": relative_path, "findings": findings}
                )
                logger.warning(f"MD5 usage found in {relative_path}")
            elif md5_found and sha256_found:
                self.migration_report["md5_found"].append(
                    {"file": relative_path, "findings": findings, "status": "partial_migration"}
                )
                logger.info(f"Mixed hash usage in {relative_path}")
            elif sha256_found and not md5_found:
                self.migration_report["migration_complete"].append(relative_path)

        except Exception as e:
            self.migration_report["errors"].append({"file": str(file_path), "error": str(e)})
            logger.error(f"Error scanning {file_path}: {e}")

    def _generate_summary(self) -> None:
        """Generate a summary of the scan results."""
        total_md5 = len(self.migration_report["migration_needed"]) + len(
            self.migration_report["md5_found"]
        )
        total_sha256 = len(self.migration_report["migration_complete"])

        self.migration_report["summary"] = {
            "total_files_scanned": self.migration_report["files_scanned"],
            "files_with_md5": total_md5,
            "files_with_sha256": total_sha256,
            "files_needing_migration": len(self.migration_report["migration_needed"]),
            "migration_percentage": (total_sha256 / max(total_md5 + total_sha256, 1)) * 100,
        }

    def validate_migration(self, file_path: Path) -> bool:
        """Validate that a file has been properly migrated."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for any remaining MD5 usage
            for pattern in self.MD5_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    # Allow MD5 only in comments or strings
                    if not self._is_safe_md5_usage(content, pattern):
                        return False

            return True
        except Exception as e:
            logger.error(f"Error validating {file_path}: {e}")
            return False

    def _is_safe_md5_usage(self, content: str, pattern: str) -> bool:
        """Check if MD5 usage is in comments or documentation."""
        lines = content.split("\n")
        for line in lines:
            if re.search(pattern, line, re.IGNORECASE):
                # Check if it's in a comment
                if "#" in line and line.index("#") < line.index("md5"):
                    continue
                # Check if it's in a docstring or string
                if '"""' in line or "'''" in line or '"md5"' in line or "'md5'" in line:
                    continue
                return False
        return True


class CacheMigrationManager:
    """Manages cache invalidation during hash migration."""

    def __init__(self, redis_client=None) -> None:
        """Initialize cache migration manager."""
        self.redis_client = redis_client
        self.migration_log = []

    def invalidate_md5_caches(self) -> Dict:
        """Invalidate all caches that use MD5-based keys."""
        result = {"caches_cleared": 0, "patterns_cleared": [], "errors": []}

        cache_patterns = [
            "api_cache:*",
            "evidence_stats:*",
            "evidence_dashboard:*",
            "business_profile:*",
            "framework_info:*",
            "func:*",
            "query_cache:*",
            "embedding_cache:*",
            "policy_cache:*",
        ]

        if self.redis_client:
            for pattern in cache_patterns:
                try:
                    keys = self.redis_client.keys(pattern)
                    if keys:
                        self.redis_client.delete(*keys)
                        result["caches_cleared"] += len(keys)
                        result["patterns_cleared"].append(pattern)
                        logger.info(f"Cleared {len(keys)} cache entries for pattern: {pattern}")
                except Exception as e:
                    result["errors"].append(f"Failed to clear {pattern}: {e}")
                    logger.error(f"Cache clear error for {pattern}: {e}")
        else:
            logger.warning("Redis client not available, skipping cache invalidation")

        return result

    def create_hash_mapping(self, old_hash: str, new_hash: str) -> None:
        """Create a mapping from old MD5 hash to new SHA256 hash."""
        self.migration_log.append(
            {"timestamp": datetime.utcnow().isoformat(), "old_hash": old_hash, "new_hash": new_hash}
        )

    def migrate_hash_value(self, value: str) -> str:
        """Migrate a single hash value from MD5 to SHA256."""
        # Generate SHA256 hash with same truncation as in the code
        return hashlib.sha256(value.encode()).hexdigest()[:16]


class RollbackManager:
    """Manages rollback capabilities for the migration."""

    def __init__(self) -> None:
        """Initialize rollback manager."""
        self.backup_dir = Path("backups/hash_migration")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, file_path: Path) -> bool:
        """Create a backup of a file before migration."""
        try:
            backup_name = f"{file_path.name}.{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.bak"
            backup_path = self.backup_dir / backup_name

            with open(file_path, "r") as source:
                content = source.read()
            with open(backup_path, "w") as backup:
                backup.write(content)

            logger.info(f"Created backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create backup for {file_path}: {e}")
            return False

    def restore_backup(self, file_path: Path, backup_timestamp: str) -> bool:
        """Restore a file from backup."""
        try:
            backup_name = f"{file_path.name}.{backup_timestamp}.bak"
            backup_path = self.backup_dir / backup_name

            if not backup_path.exists():
                logger.error(f"Backup not found: {backup_path}")
                return False

            with open(backup_path, "r") as backup:
                content = backup.read()
            with open(file_path, "w") as target:
                target.write(content)

            logger.info(f"Restored {file_path} from backup")
            return True
        except Exception as e:
            logger.error(f"Failed to restore {file_path}: {e}")
            return False


def run_ci_check() -> int:
    """Run CI check to prevent MD5 regression."""
    project_root = Path(__file__).parent.parent
    validator = HashMigrationValidator(project_root)

    report = validator.scan_codebase()

    # Check for any files needing migration
    if report["migration_needed"]:
        logger.error("CI Check Failed: MD5 usage found in the following files:")
        for file_info in report["migration_needed"]:
            logger.error(f"  - {file_info['file']}")
            for finding in file_info["findings"]:
                if finding["type"] == "MD5":
                    logger.error(f"    Line {finding['line']}: {finding['content']}")
        return 1

    logger.info(
        f"CI Check Passed: {report['summary']['migration_percentage']:.1f}% of files use SHA-256"
    )
    return 0


def generate_migration_report(output_file: str = "hash_migration_report.json") -> None:
    """Generate a detailed migration report."""
    project_root = Path(__file__).parent.parent
    validator = HashMigrationValidator(project_root)

    report = validator.scan_codebase()

    # Save report to file
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "=" * 50)
    print("Hash Migration Report")
    print("=" * 50)
    print(f"Total files scanned: {report['summary']['total_files_scanned']}")
    print(f"Files with MD5: {report['summary']['files_with_md5']}")
    print(f"Files with SHA-256: {report['summary']['files_with_sha256']}")
    print(f"Files needing migration: {report['summary']['files_needing_migration']}")
    print(f"Migration progress: {report['summary']['migration_percentage']:.1f}%")

    if report["migration_needed"]:
        print("\nFiles requiring migration:")
        for file_info in report["migration_needed"]:
            print(f"  - {file_info['file']}")

    if report["errors"]:
        print("\nErrors encountered:")
        for error in report["errors"]:
            print(f"  - {error['file']}: {error['error']}")

    print(f"\nDetailed report saved to: {output_file}")


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(description="Security Hash Migration Tool")
    parser.add_argument(
        "command", choices=["scan", "validate", "ci-check", "report"], help="Command to run"
    )
    parser.add_argument("--file", help="Specific file to validate")
    parser.add_argument(
        "--output", default="hash_migration_report.json", help="Output file for report"
    )

    args = parser.parse_args()

    if args.command == "scan":
        project_root = Path(__file__).parent.parent
        validator = HashMigrationValidator(project_root)
        report = validator.scan_codebase()
        print(json.dumps(report["summary"], indent=2))

    elif args.command == "validate":
        if not args.file:
            print("Error: --file required for validate command")
            sys.exit(1)
        project_root = Path(__file__).parent.parent
        validator = HashMigrationValidator(project_root)
        file_path = Path(args.file)
        if validator.validate_migration(file_path):
            print(f"✓ {file_path} is properly migrated")
        else:
            print(f"✗ {file_path} still contains insecure hash usage")
            sys.exit(1)

    elif args.command == "ci-check":
        sys.exit(run_ci_check())

    elif args.command == "report":
        generate_migration_report(args.output)


if __name__ == "__main__":
    main()
