#!/usr/bin/env python3
"""
Cache Security Validation Script

Scans caching modules for security violations including:
- MD5/SHA1 usage (should use SHA-256)
- Bare except clauses
- Hardcoded secrets
- Insecure practices

Usage:
    python scripts/validate_cache_security.py

Returns:
    0 if all checks pass
    1 if security violations found
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import Dict

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Color codes for terminal output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class CacheSecurityValidator:
    """Validates security practices in caching modules"""

    def __init__(self) -> None:
        self.violations = []
        self.warnings = []
        self.cache_dir = Path("services/caching")
        self.checked_files = 0

    def add_violation(self, file: str, line: int, message: str, code: str = ""):
        """Add a security violation"""
        self.violations.append({"file": file, "line": line, "message": message, "code": code})

    def add_warning(self, file: str, line: int, message: str, code: str = ""):
        """Add a security warning"""
        self.warnings.append({"file": file, "line": line, "message": message, "code": code})

    def check_insecure_hash(self, file_path: Path) -> None:
        """Check for MD5/SHA1 usage"""
        content = file_path.read_text()
        lines = content.split("\n")

        # Patterns for insecure hash usage
        insecure_patterns = [
            (r"hashlib\.md5\(", "MD5 hash detected (S324)"),
            (r"hashlib\.sha1\(", "SHA1 hash detected (S324)"),
            (r"\.md5\(", "MD5 usage detected (S324)"),
            (r"\.sha1\(", "SHA1 usage detected (S324)"),
            (r"from hashlib import md5", "MD5 import detected (S324)"),
            (r"from hashlib import sha1", "SHA1 import detected (S324)"),
        ]

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("#"):
                continue

            for pattern, message in insecure_patterns:
                if re.search(pattern, line):
                    # Check if line has noqa comment (case-insensitive)
                    if "# noqa: s324" in line.lower():
                        self.add_warning(
                            str(file_path),
                            line_num,
                            f"{message} - has noqa comment for migration",
                            line.strip(),
                        )
                    # Check if it's in a compatibility/migration context
                    elif (
                        "migration" in line.lower()
                        or "legacy" in line.lower()
                        or "fallback" in line.lower()
                    ):
                        self.add_warning(
                            str(file_path),
                            line_num,
                            f"{message} - appears to be for migration/compatibility",
                            line.strip(),
                        )
                    # Check if previous lines contain legacy/migration/fallback context
                    elif line_num > 1:
                        # Check previous 2 lines for context
                        prev_lines = lines[max(0, line_num - 3) : line_num - 1]
                        if any(
                            "legacy" in l.lower()
                            or "migration" in l.lower()
                            or "fallback" in l.lower()
                            for l in prev_lines
                        ):
                            self.add_warning(
                                str(file_path),
                                line_num,
                                f"{message} - appears to be in migration context",
                                line.strip(),
                            )
                        else:
                            self.add_violation(str(file_path), line_num, message, line.strip())
                    else:
                        self.add_violation(str(file_path), line_num, message, line.strip())

    def check_bare_except(self, file_path: Path) -> None:
        """Check for bare except clauses"""
        content = file_path.read_text()

        try:
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:  # Bare except
                        self.add_violation(
                            str(file_path),
                            node.lineno,
                            "Bare except clause detected (S110/S112)",
                            "except:",
                        )
                    elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                        # Check if it's a broad Exception handler
                        line = (
                            content.split("\n")[node.lineno - 1]
                            if node.lineno <= len(content.split("\n"))
                            else ""
                        )

                        # Allow if it re-raises or logs at error level
                        following_lines = content.split("\n")[node.lineno : node.lineno + 5]
                        if not any("raise" in line for line in following_lines):
                            self.add_warning(
                                str(file_path),
                                node.lineno,
                                "Broad Exception handler without re-raise",
                                line.strip(),
                            )
        except SyntaxError as e:
            print(f"{YELLOW}Warning: Could not parse {file_path}: {e}{RESET}")

    def check_hardcoded_secrets(self, file_path: Path) -> None:
        """Check for hardcoded secrets or passwords"""
        content = file_path.read_text()
        lines = content.split("\n")

        # Patterns for potential secrets
        secret_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password detected (S105)"),
            (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret detected (S105)"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key detected (S105)"),
            (r'token\s*=\s*["\'][^"\']+["\']', "Hardcoded token detected (S105)"),
            (r'private_key\s*=\s*["\'][^"\']+["\']', "Hardcoded private key detected (S105)"),
        ]

        for line_num, line in enumerate(lines, 1):
            # Skip comments and docstrings
            if line.strip().startswith("#") or '"""' in line or "'''" in line:
                continue

            for pattern, message in secret_patterns:
                if re.search(pattern, line.lower()):
                    # Check if it's a placeholder or example
                    if any(
                        placeholder in line.lower()
                        for placeholder in ["example", "placeholder", "your_", "xxx", "***", "..."]
                    ):
                        continue

                    self.add_violation(str(file_path), line_num, message, line.strip())

    def check_magic_values(self, file_path: Path) -> None:
        """Check for magic values that should be constants"""
        content = file_path.read_text()
        lines = content.split("\n")

        # Common magic values that should be constants
        magic_patterns = [
            (r"ttl=\d{3,}(?!\d)", "Magic TTL value should be a constant"),
            (r"max_items=\d{3,}(?!\d)", "Magic max_items value should be a constant"),
            (r"timeout=\d{3,}(?!\d)", "Magic timeout value should be a constant"),
        ]

        for line_num, line in enumerate(lines, 1):
            # Skip comments and constant definitions
            if line.strip().startswith("#") or "=" in line and line.split("=")[0].strip().isupper():
                continue

            for pattern, message in magic_patterns:
                if re.search(pattern, line):
                    self.add_warning(str(file_path), line_num, message, line.strip())

    def check_redis_exception_handling(self, file_path: Path) -> None:
        """Check for proper Redis exception handling"""
        content = file_path.read_text()

        # Check if file uses Redis
        if "redis" not in content.lower():
            return

        # Check for proper Redis exception imports
        if "from redis.exceptions import" not in content and "RedisError" not in content:
            if "self._redis" in content or "redis.get(" in content or "redis.set(" in content:
                self.add_warning(
                    str(file_path),
                    1,
                    "Redis operations found but no Redis-specific exception handling imported",
                    "",
                )

    def validate_file(self, file_path: Path) -> None:
        """Validate a single Python file"""
        if file_path.suffix != ".py":
            return

        print(f"Checking {file_path}...")
        self.checked_files += 1

        self.check_insecure_hash(file_path)
        self.check_bare_except(file_path)
        self.check_hardcoded_secrets(file_path)
        self.check_magic_values(file_path)
        self.check_redis_exception_handling(file_path)

    def validate_all(self) -> bool:
        """Validate all caching module files"""
        if not self.cache_dir.exists():
            print(f"{RED}Error: Caching directory {self.cache_dir} not found{RESET}")
            return False

        # Get all Python files in caching directory
        py_files = list(self.cache_dir.glob("*.py"))

        if not py_files:
            print(f"{YELLOW}Warning: No Python files found in {self.cache_dir}{RESET}")
            return True

        print(f"{BLUE}Validating {len(py_files)} files in {self.cache_dir}{RESET}\n")

        for file_path in py_files:
            self.validate_file(file_path)

        return len(self.violations) == 0

    def print_results(self) -> None:
        """Print validation results"""
        print("\n" + "=" * 60)
        print(f"{BLUE}Cache Security Validation Results{RESET}")
        print("=" * 60)

        print(f"\nFiles checked: {self.checked_files}")

        if self.violations:
            print(f"\n{RED}❌ VIOLATIONS FOUND ({len(self.violations)} issues){RESET}\n")
            for violation in self.violations:
                print(f"{RED}✗ {violation['file']}:{violation['line']}{RESET}")
                print(f"  {violation['message']}")
                if violation["code"]:
                    print(f"  Code: {violation['code'][:80]}")
                print()

        if self.warnings:
            print(f"\n{YELLOW}⚠️  WARNINGS ({len(self.warnings)} issues){RESET}\n")
            for warning in self.warnings:
                print(f"{YELLOW}! {warning['file']}:{warning['line']}{RESET}")
                print(f"  {warning['message']}")
                if warning["code"]:
                    print(f"  Code: {warning['code'][:80]}")
                print()

        if not self.violations and not self.warnings:
            print(f"\n{GREEN}✅ All security checks passed!{RESET}")
            print("No security violations or warnings found in caching modules.\n")
        elif not self.violations:
            print(f"\n{GREEN}✅ No critical violations found{RESET}")
            print(f"{YELLOW}But {len(self.warnings)} warnings need review{RESET}\n")
        else:
            print(f"\n{RED}❌ Security validation FAILED{RESET}")
            print(f"Found {len(self.violations)} violations that must be fixed\n")

        print("=" * 60)

    def generate_report(self) -> Dict:
        """Generate a JSON report of findings"""
        return {
            "checked_files": self.checked_files,
            "violations": self.violations,
            "warnings": self.warnings,
            "passed": len(self.violations) == 0,
        }


def main() -> int:
    """Main entry point"""
    print(f"{BLUE}Starting Cache Security Validation...{RESET}\n")

    validator = CacheSecurityValidator()

    # Run validation
    passed = validator.validate_all()

    # Print results
    validator.print_results()

    # Generate report (could be saved to file)
    validator.generate_report()

    # Return appropriate exit code
    if not passed:
        print(f"\n{RED}Validation failed! Fix violations before committing.{RESET}")
        return 1

    if validator.warnings:
        print(f"\n{YELLOW}Validation passed with warnings. Please review.{RESET}")
    else:
        print(f"\n{GREEN}All validations passed successfully!{RESET}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
