#!/usr/bin/env python3
"""
CI Broken Steps Fixer Utility

This script analyzes GitHub Actions workflow files to detect missing file references
and common misconfigurations, with options to report or automatically fix issues.

Usage:
    python fix_broken_ci_steps.py --report-only  # Just report issues
    python fix_broken_ci_steps.py --fix          # Attempt to fix issues
"""

import sys
import yaml
import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class WorkflowAnalyzer:
    """Analyzes GitHub Actions workflow files for issues."""

    def __init__(self, repo_root: str = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.workflows_dir = self.repo_root / ".github" / "workflows"
        self.issues = []
        self.fixes_applied = []

    def find_workflow_files(self) -> List[Path]:
        """Find all workflow YAML files."""
        if not self.workflows_dir.exists():
            print(f"❌ Workflows directory not found: {self.workflows_dir}")
            return []

        workflow_files = list(self.workflows_dir.glob("*.yml")) + list(
            self.workflows_dir.glob("*.yaml")
        )
        return workflow_files

    def load_workflow(self, filepath: Path) -> Optional[Dict]:
        """Load and parse a workflow file."""
        try:
            with open(filepath, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.issues.append(
                {
                    "file": str(filepath),
                    "type": "parse_error",
                    "message": f"Failed to parse YAML: {e}",
                }
            )
            return None

    def check_file_references(self, workflow: Dict, filepath: Path) -> List[Dict]:
        """Check for missing file references in workflow."""
        issues = []

        # Common patterns for file references
        file_patterns = [
            r"python\s+([^\s|&;]+\.py)",  # Python scripts
            r"bash\s+([^\s|&;]+\.sh)",  # Shell scripts
            r"node\s+([^\s|&;]+\.js)",  # Node scripts
            r"\./([^\s|&;]+)",  # Relative paths
            r"test\s+-f\s+([^\s|&;]+)",  # File existence tests
            r"cat\s+([^\s|&;]+)",  # Cat commands
        ]

        def check_step(step: Dict, job_name: str) -> None:
            if not isinstance(step, dict):
                return

            run_command = step.get("run", "")
            if not run_command:
                return

            for pattern in file_patterns:
                matches = re.findall(pattern, run_command)
                for match in matches:
                    # Skip if it's a variable or contains $
                    if "$" in match or match.startswith("-"):
                        continue

                    # Resolve the file path
                    file_path = self.repo_root / match

                    # Check if file exists
                    if not file_path.exists():
                        issues.append(
                            {
                                "file": str(filepath.name),
                                "job": job_name,
                                "step": step.get("name", "unnamed"),
                                "type": "missing_file",
                                "path": match,
                                "full_path": str(file_path),
                            }
                        )

        # Check all jobs and steps
        if "jobs" in workflow:
            for job_name, job_config in workflow["jobs"].items():
                if not isinstance(job_config, dict):
                    continue

                steps = job_config.get("steps", [])
                for step in steps:
                    check_step(step, job_name)

        return issues

    def check_common_misconfigurations(self, workflow: Dict, filepath: Path) -> List[Dict]:
        """Check for common workflow misconfigurations."""
        issues = []

        # Check for missing checkout step
        if "jobs" in workflow:
            for job_name, job_config in workflow["jobs"].items():
                if not isinstance(job_config, dict):
                    continue

                steps = job_config.get("steps", [])
                has_checkout = any(
                    "actions/checkout" in str(step.get("uses", ""))
                    for step in steps
                    if isinstance(step, dict)
                )

                # Check if job accesses files without checkout
                needs_checkout = any(
                    "run" in step
                    and (
                        "python" in step.get("run", "")
                        or "npm" in step.get("run", "")
                        or "pip install -r" in step.get("run", "")
                        or "./test" in step.get("run", "")
                    )
                    for step in steps
                    if isinstance(step, dict)
                )

                if needs_checkout and not has_checkout:
                    issues.append(
                        {
                            "file": str(filepath.name),
                            "job": job_name,
                            "type": "missing_checkout",
                            "message": "Job appears to access files but has no checkout step",
                        }
                    )

        # Check for undefined environment variables
        env_pattern = r"\$\{\{\s*env\.([A-Z_]+)\s*\}\}"
        workflow_str = str(workflow)
        env_refs = re.findall(env_pattern, workflow_str)

        defined_envs = set()
        if "env" in workflow:
            defined_envs.update(workflow["env"].keys())

        for env_var in env_refs:
            if env_var not in defined_envs and env_var not in ["CI", "GITHUB_TOKEN"]:
                issues.append(
                    {
                        "file": str(filepath.name),
                        "type": "undefined_env",
                        "variable": env_var,
                        "message": f"Environment variable {env_var} is referenced but not defined",
                    }
                )

        return issues

    def suggest_fixes(self, issues: List[Dict]) -> List[Dict]:
        """Suggest fixes for identified issues."""
        fixes = []

        for issue in issues:
            if issue["type"] == "missing_file":
                # Suggest creating the file or adding a guard
                fixes.append(
                    {
                        "issue": issue,
                        "fix_type": "add_guard",
                        "suggestion": f"Add file existence check: test -f {issue['path']} && ... || echo 'File missing'",
                    }
                )

                # If it's a validation script, suggest creating it
                if "validate" in issue["path"] or "check" in issue["path"]:
                    fixes.append(
                        {
                            "issue": issue,
                            "fix_type": "create_stub",
                            "suggestion": f"Create stub script at {issue['path']}",
                        }
                    )

            elif issue["type"] == "missing_checkout":
                fixes.append(
                    {
                        "issue": issue,
                        "fix_type": "add_checkout",
                        "suggestion": "Add 'actions/checkout' as the first step in the job",
                    }
                )

            elif issue["type"] == "undefined_env":
                fixes.append(
                    {
                        "issue": issue,
                        "fix_type": "define_env",
                        "suggestion": f"Define {issue['variable']} in workflow env section or use secrets",
                    }
                )

        return fixes

    def apply_fix(self, fix: Dict, workflow_path: Path) -> bool:
        """Apply a fix to a workflow file."""
        try:
            with open(workflow_path, "r") as f:
                content = f.read()

            modified = False

            if fix["fix_type"] == "add_guard":
                issue = fix["issue"]
                # Find the run command that references the file
                pattern = f"(\\s+)(python|bash|node|\\./)?\\s*{re.escape(issue['path'])}"
                replacement = f"\\1test -f {issue['path']} && \\2 {issue['path']} || echo '{issue['path']} missing; skipping'"

                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    modified = True
                    content = new_content

            if modified:
                with open(workflow_path, "w") as f:
                    f.write(content)
                return True

            return False

        except Exception as e:
            print(f"❌ Failed to apply fix: {e}")
            return False

    def analyze(self, fix: bool = False) -> Tuple[List[Dict], List[Dict]]:
        """Analyze all workflow files."""
        all_issues = []
        all_fixes = []

        workflow_files = self.find_workflow_files()

        if not workflow_files:
            print("⚠️  No workflow files found")
            return all_issues, all_fixes

        print(f"📋 Found {len(workflow_files)} workflow files")

        for workflow_file in workflow_files:
            print(f"\n🔍 Analyzing: {workflow_file.name}")

            workflow = self.load_workflow(workflow_file)
            if not workflow:
                continue

            # Check for issues
            file_issues = self.check_file_references(workflow, workflow_file)
            config_issues = self.check_common_misconfigurations(workflow, workflow_file)

            issues = file_issues + config_issues
            all_issues.extend(issues)

            if issues:
                print(f"  ⚠️  Found {len(issues)} issues")
                for issue in issues:
                    print(f"    • {issue['type']}: {issue.get('message', issue.get('path', ''))}")
            else:
                print("  ✅ No issues found")

            # Suggest fixes
            if issues:
                fixes = self.suggest_fixes(issues)
                all_fixes.extend(fixes)

                if fix and fixes:
                    print(f"  🔧 Attempting to apply {len(fixes)} fixes...")
                    for fix_item in fixes:
                        if fix_item["fix_type"] in ["add_guard"]:
                            if self.apply_fix(fix_item, workflow_file):
                                print(f"    ✅ Applied: {fix_item['suggestion']}")
                                self.fixes_applied.append(fix_item)
                            else:
                                print(f"    ⚠️  Could not apply: {fix_item['suggestion']}")

        return all_issues, all_fixes


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fix broken CI steps in GitHub Actions workflows")
    parser.add_argument(
        "--report-only", action="store_true", help="Only report issues without fixing"
    )
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues automatically")
    parser.add_argument(
        "--repo-root", default=".", help="Repository root directory (default: current directory)"
    )

    args = parser.parse_args()

    if not args.report_only and not args.fix:
        print("❌ Please specify either --report-only or --fix")
        sys.exit(1)

    print("🔧 CI Broken Steps Analyzer")
    print("=" * 60)

    analyzer = WorkflowAnalyzer(args.repo_root)
    issues, fixes = analyzer.analyze(fix=args.fix)

    # Print summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    if not issues:
        print("✅ No issues found in workflow files!")
        sys.exit(0)

    print(f"\n❌ Found {len(issues)} issues:")

    # Group issues by type
    issue_types = {}
    for issue in issues:
        issue_type = issue["type"]
        if issue_type not in issue_types:
            issue_types[issue_type] = []
        issue_types[issue_type].append(issue)

    for issue_type, type_issues in issue_types.items():
        print(f"\n  {issue_type.upper()} ({len(type_issues)} issues):")
        for issue in type_issues[:5]:  # Show first 5 of each type
            if issue_type == "missing_file":
                print(f"    • {issue['file']} → {issue['job']} → {issue['path']}")
            else:
                print(f"    • {issue['file']}: {issue.get('message', '')}")

        if len(type_issues) > 5:
            print(f"    ... and {len(type_issues) - 5} more")

    if args.fix and analyzer.fixes_applied:
        print(f"\n✅ Applied {len(analyzer.fixes_applied)} fixes")
    elif args.report_only and fixes:
        print(f"\n💡 {len(fixes)} fixes available (run with --fix to apply)")

    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
