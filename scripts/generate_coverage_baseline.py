#!/usr/bin/env python3
"""
Coverage Baseline Generation Script for RuleIQ

Parses coverage reports from backend (pytest-cov) and frontend (vitest)
and generates a comprehensive baseline metrics document.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET


class CoverageBaselineGenerator:
    """Generates coverage baseline documentation from test artifacts."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = project_root or Path(__file__).parent.parent
        self.backend_coverage_xml = self.project_root / "coverage.xml"
        self.backend_coverage_json = self.project_root / "coverage.json"
        self.frontend_coverage_summary = (
            self.project_root / "frontend" / "coverage" / "coverage-summary.json"
        )
        self.frontend_lcov = (
            self.project_root / "frontend" / "coverage" / "lcov.info"
        )
        self.output_file = self.project_root / "docs" / "COVERAGE_BASELINE.md"

    def parse_backend_coverage_xml(self) -> Dict:
        """Parse backend coverage.xml for overall and per-package metrics."""
        if not self.backend_coverage_xml.exists():
            print(f"⚠️  Backend coverage.xml not found: {self.backend_coverage_xml}")
            return {}

        try:
            tree = ET.parse(self.backend_coverage_xml)
            root = tree.getroot()

            # Overall coverage
            overall_line_rate = float(root.attrib.get("line-rate", 0)) * 100
            overall_branch_rate = float(root.attrib.get("branch-rate", 0)) * 100

            # Per-package coverage
            packages = {}
            for package in root.findall(".//package"):
                pkg_name = package.attrib.get("name", "unknown")
                line_rate = float(package.attrib.get("line-rate", 0)) * 100
                branch_rate = float(package.attrib.get("branch-rate", 0)) * 100

                # Count lines and branches from all <line> elements in this package
                lines_valid = 0
                branches_valid = 0
                for line in package.findall(".//line"):
                    lines_valid += 1
                    # Check if this line has branch coverage
                    if line.attrib.get("branch") == "true":
                        # Extract number of branches from condition-coverage attribute
                        cond_cov = line.attrib.get("condition-coverage", "0% (0/0)")
                        # Parse format like "0% (0/2)" to get total branches
                        if "/" in cond_cov:
                            branches_valid += int(cond_cov.split("/")[-1].rstrip(")"))

                packages[pkg_name] = {
                    "line_coverage": line_rate,
                    "branch_coverage": branch_rate,
                    "lines_valid": lines_valid,
                    "branches_valid": branches_valid,
                }

            return {
                "overall_line": overall_line_rate,
                "overall_branch": overall_branch_rate,
                "packages": packages,
            }

        except Exception as e:
            print(f"⚠️  Error parsing backend coverage XML: {e}")
            return {}

    def parse_backend_coverage_json(self) -> Dict:
        """Parse backend coverage.json for detailed file-level metrics."""
        if not self.backend_coverage_json.exists():
            print(f"⚠️  Backend coverage.json not found: {self.backend_coverage_json}")
            return {}

        try:
            with open(self.backend_coverage_json) as f:
                data = json.load(f)

            # Extract file-level coverage
            files = {}
            for file_path, file_data in data.get("files", {}).items():
                summary = file_data.get("summary", {})
                files[file_path] = {
                    "line_coverage": summary.get("percent_covered", 0),
                    "num_statements": summary.get("num_statements", 0),
                    "covered_lines": summary.get("covered_lines", 0),
                    "missing_lines": summary.get("missing_lines", 0),
                }

            # Overall totals
            totals = data.get("totals", {})

            return {
                "overall_line": totals.get("percent_covered", 0),
                "files": files,
            }

        except Exception as e:
            print(f"⚠️  Error parsing backend coverage JSON: {e}")
            return {}

    def parse_frontend_coverage(self) -> Dict:
        """Parse frontend coverage-summary.json."""
        if not self.frontend_coverage_summary.exists():
            print(
                f"⚠️  Frontend coverage summary not found: {self.frontend_coverage_summary}"
            )
            return {}

        try:
            with open(self.frontend_coverage_summary) as f:
                data = json.load(f)

            # Overall totals
            total = data.get("total", {})
            overall = {
                "line_coverage": total.get("lines", {}).get("pct", 0),
                "branch_coverage": total.get("branches", {}).get("pct", 0),
                "function_coverage": total.get("functions", {}).get("pct", 0),
                "statement_coverage": total.get("statements", {}).get("pct", 0),
            }

            # Per-directory coverage
            directories = {}
            for path, metrics in data.items():
                if path == "total":
                    continue

                # Extract directory from path
                path_obj = Path(path)
                directory = path_obj.parts[0] if len(path_obj.parts) > 0 else "root"

                if directory not in directories:
                    directories[directory] = {
                        "files": 0,
                        "total_lines": 0,
                        "covered_lines": 0,
                    }

                directories[directory]["files"] += 1
                lines = metrics.get("lines", {})
                directories[directory]["total_lines"] += lines.get("total", 0)
                directories[directory]["covered_lines"] += lines.get("covered", 0)

            # Calculate directory percentages
            for _dir_name, stats in directories.items():
                if stats["total_lines"] > 0:
                    stats["line_coverage"] = (
                        stats["covered_lines"] / stats["total_lines"]
                    ) * 100
                else:
                    stats["line_coverage"] = 0

            return {
                "overall": overall,
                "directories": directories,
            }

        except Exception as e:
            print(f"⚠️  Error parsing frontend coverage: {e}")
            return {}

    def get_top_covered_files(self, files: Dict, limit: int = 10) -> List[Tuple]:
        """Get top N most covered files."""
        sorted_files = sorted(
            files.items(), key=lambda x: x[1].get("line_coverage", 0), reverse=True
        )
        return sorted_files[:limit]

    def get_least_covered_files(self, files: Dict, limit: int = 10) -> List[Tuple]:
        """Get top N least covered files (excluding 0% coverage)."""
        filtered_files = {
            k: v for k, v in files.items() if v.get("line_coverage", 0) > 0
        }
        sorted_files = sorted(
            filtered_files.items(), key=lambda x: x[1].get("line_coverage", 0)
        )
        return sorted_files[:limit]

    def get_critical_uncovered_files(self, files: Dict) -> List[str]:
        """Identify critical files with low or no coverage."""
        critical_patterns = [
            "auth",
            "security",
            "payment",
            "compliance",
            "assessment",
        ]
        critical_uncovered = []

        for file_path, metrics in files.items():
            coverage = metrics.get("line_coverage", 0)
            if coverage < 50:  # Less than 50% coverage
                for pattern in critical_patterns:
                    if pattern in file_path.lower():
                        critical_uncovered.append(file_path)
                        break

        return critical_uncovered

    def generate_baseline_document(self) -> str:
        """Generate comprehensive baseline markdown document."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Parse coverage data
        backend_xml = self.parse_backend_coverage_xml()
        backend_json = self.parse_backend_coverage_json()
        frontend = self.parse_frontend_coverage()

        # Calculate combined coverage (weighted by lines of code)
        backend_line_cov = backend_xml.get("overall_line", 0)
        frontend_line_cov = frontend.get("overall", {}).get("line_coverage", 0)

        # Simple average for now (can be weighted later)
        if backend_line_cov and frontend_line_cov:
            combined_coverage = (backend_line_cov + frontend_line_cov) / 2
        else:
            combined_coverage = backend_line_cov or frontend_line_cov or 0

        doc = f"""# Coverage Baseline Report

**Generated**: {timestamp}
**Project**: RuleIQ Compliance Automation Platform
**Purpose**: Establish test coverage baseline for quality gate enforcement

---

## Executive Summary

### Overall Project Coverage

| Metric | Coverage | Target | Status |
|--------|----------|--------|--------|
| **Combined Project** | {combined_coverage:.2f}% | 80% | {"🟢 Good" if combined_coverage >= 80 else "🟡 Needs Improvement" if combined_coverage >= 50 else "🔴 Critical"} |
| **Backend (Python)** | {backend_line_cov:.2f}% | 80% | {"🟢 Good" if backend_line_cov >= 80 else "🟡 Needs Improvement" if backend_line_cov >= 50 else "🔴 Critical"} |
| **Frontend (TypeScript)** | {frontend_line_cov:.2f}% | 80% | {"🟢 Good" if frontend_line_cov >= 80 else "🟡 Needs Improvement" if frontend_line_cov >= 50 else "🔴 Critical"} |

### Key Findings

"""

        if combined_coverage < 50:
            doc += "- 🔴 **Critical**: Overall coverage is below 50% - urgent action required\n"
        elif combined_coverage < 80:
            doc += "- 🟡 **Action Required**: Coverage needs significant improvement to meet industry standards\n"
        else:
            doc += "- 🟢 **Good**: Coverage meets or exceeds industry standards\n"

        doc += f"""
- Current baseline established as of {timestamp}
- Coverage data collected from pytest-cov (backend) and vitest (frontend)
- Quality gates will enforce maintenance of this baseline

---

## Backend Coverage (Python)

### Overall Backend Metrics

| Type | Coverage | Status |
|------|----------|--------|
| **Line Coverage** | {backend_xml.get('overall_line', 0):.2f}% | {"✅" if backend_xml.get('overall_line', 0) >= 80 else "⚠️"} |
| **Branch Coverage** | {backend_xml.get('overall_branch', 0):.2f}% | {"✅" if backend_xml.get('overall_branch', 0) >= 70 else "⚠️"} |

### Per-Module Breakdown

| Module | Line Coverage | Branch Coverage | Status |
|--------|--------------|-----------------|--------|
"""

        # Backend packages
        packages = backend_xml.get("packages", {})
        for pkg_name, metrics in sorted(
            packages.items(), key=lambda x: x[1].get("line_coverage", 0), reverse=True
        ):
            line_cov = metrics.get("line_coverage", 0)
            branch_cov = metrics.get("branch_coverage", 0)
            status = "🟢" if line_cov >= 80 else "🟡" if line_cov >= 50 else "🔴"
            doc += f"| `{pkg_name}` | {line_cov:.2f}% | {branch_cov:.2f}% | {status} |\n"

        # Top covered files
        backend_files = backend_json.get("files", {})
        if backend_files:
            doc += "\n### Top 10 Most Covered Files\n\n"
            doc += "| File | Coverage | Status |\n"
            doc += "|------|----------|--------|\n"

            top_files = self.get_top_covered_files(backend_files)
            for file_path, metrics in top_files:
                coverage = metrics.get("line_coverage", 0)
                status = "✅"
                doc += f"| `{file_path}` | {coverage:.2f}% | {status} |\n"

            # Least covered files
            doc += "\n### Top 10 Least Covered Files (Priority for Improvement)\n\n"
            doc += "| File | Coverage | Priority |\n"
            doc += "|------|----------|----------|\n"

            least_files = self.get_least_covered_files(backend_files)
            for file_path, metrics in least_files:
                coverage = metrics.get("line_coverage", 0)
                priority = "🔴 High" if coverage < 30 else "🟡 Medium"
                doc += f"| `{file_path}` | {coverage:.2f}% | {priority} |\n"

            # Critical uncovered paths
            critical = self.get_critical_uncovered_files(backend_files)
            if critical:
                doc += "\n### Critical Uncovered Paths\n\n"
                doc += "⚠️  **These files handle sensitive operations and require immediate coverage:**\n\n"
                for file_path in critical:
                    coverage = backend_files[file_path].get("line_coverage", 0)
                    doc += f"- `{file_path}` - {coverage:.2f}% coverage\n"

        doc += "\n---\n\n## Frontend Coverage (TypeScript/React)\n\n"

        # Frontend overall metrics
        frontend_overall = frontend.get("overall", {})
        doc += "### Overall Frontend Metrics\n\n"
        doc += "| Type | Coverage | Status |\n"
        doc += "|------|----------|--------|\n"
        doc += f"| **Line Coverage** | {frontend_overall.get('line_coverage', 0):.2f}% | {'✅' if frontend_overall.get('line_coverage', 0) >= 80 else '⚠️'} |\n"
        doc += f"| **Branch Coverage** | {frontend_overall.get('branch_coverage', 0):.2f}% | {'✅' if frontend_overall.get('branch_coverage', 0) >= 70 else '⚠️'} |\n"
        doc += f"| **Function Coverage** | {frontend_overall.get('function_coverage', 0):.2f}% | {'✅' if frontend_overall.get('function_coverage', 0) >= 80 else '⚠️'} |\n"
        doc += f"| **Statement Coverage** | {frontend_overall.get('statement_coverage', 0):.2f}% | {'✅' if frontend_overall.get('statement_coverage', 0) >= 80 else '⚠️'} |\n"

        # Frontend directories
        directories = frontend.get("directories", {})
        if directories:
            doc += "\n### Per-Directory Breakdown\n\n"
            doc += "| Directory | Files | Line Coverage | Status |\n"
            doc += "|-----------|-------|---------------|--------|\n"

            for dir_name, stats in sorted(
                directories.items(),
                key=lambda x: x[1].get("line_coverage", 0),
                reverse=True,
            ):
                coverage = stats.get("line_coverage", 0)
                files = stats.get("files", 0)
                status = "🟢" if coverage >= 80 else "🟡" if coverage >= 50 else "🔴"
                doc += f"| `{dir_name}/` | {files} | {coverage:.2f}% | {status} |\n"

        doc += f"""

---

## Coverage Trends

### Historical Data

This is the initial baseline. Future reports will show trends over time.

### Coverage Improvement Targets

| Timeframe | Backend Target | Frontend Target | Combined Target |
|-----------|---------------|-----------------|-----------------|
| **Current** | {backend_line_cov:.2f}% | {frontend_line_cov:.2f}% | {combined_coverage:.2f}% |
| **3 Months** | {min(backend_line_cov + 15, 60):.2f}% | {min(frontend_line_cov + 15, 60):.2f}% | {min(combined_coverage + 15, 60):.2f}% |
| **6 Months** | {min(backend_line_cov + 30, 75):.2f}% | {min(frontend_line_cov + 30, 75):.2f}% | {min(combined_coverage + 30, 75):.2f}% |
| **12 Months** | 80% | 80% | 80% |

### Planned Initiatives

1. **Q1 2025**: Focus on critical path coverage (authentication, payments, compliance)
2. **Q2 2025**: Increase integration test coverage
3. **Q3 2025**: Add E2E test coverage for core user flows
4. **Q4 2025**: Achieve 80% coverage target

---

## Quality Gates

### Current Thresholds (Enforced in CI/CD)

- **Backend Minimum**: {backend_line_cov:.2f}% (current baseline)
- **Frontend Minimum**: {frontend_line_cov:.2f}% (current baseline)
- **PR Requirement**: No coverage decrease >2% without justification

### Exceptions

Modules below baseline require explicit approval for coverage decreases:
- All modules currently below 50% coverage
- Critical security and compliance modules

---

## Recommendations

### Quick Wins (High Impact, Low Effort)

"""

        # Identify quick win opportunities
        if backend_files:
            small_uncovered = {
                k: v
                for k, v in backend_files.items()
                if v.get("num_statements", 0) < 50
                and v.get("line_coverage", 0) < 50
            }
            if small_uncovered:
                doc += "\n**Backend:**\n"
                for file_path in list(small_uncovered.keys())[:5]:
                    statements = backend_files[file_path].get("num_statements", 0)
                    doc += f"- `{file_path}` ({statements} statements) - Small file, easy to test\n"

        doc += """

### High-Priority Modules

1. **Authentication & Security**: Critical for system security
2. **Payment Processing**: Financial transaction integrity
3. **Compliance Logic**: Core business functionality
4. **API Endpoints**: User-facing functionality

### Testing Strategy Improvements

1. **Increase Unit Test Coverage**: Focus on business logic and utilities
2. **Add Integration Tests**: Test component interactions
3. **Expand E2E Tests**: Cover critical user workflows
4. **Mock External Services**: Improve test reliability and speed

### Tooling Enhancements

1. **Coverage Badges**: Add to README for visibility
2. **Coverage Trends**: Track historical data
3. **SonarCloud Integration**: Fix path mapping for accurate reporting
4. **Automated Alerts**: Notify team of coverage drops

---

## Appendix

### Viewing Coverage Reports

**Backend (HTML):**
```bash
open htmlcov/index.html
```

**Frontend (HTML):**
```bash
open frontend/coverage/index.html
```

### Running Coverage Locally

**Backend:**
```bash
pytest --cov=services --cov=api --cov=core --cov=utils --cov=models \\
       --cov-report=html --cov-report=xml --cov-branch
```

**Frontend:**
```bash
cd frontend && pnpm test:coverage
```

### CI/CD Workflows

- Backend Tests: `.github/workflows/backend-tests.yml`
- Frontend Tests: `.github/workflows/frontend-tests.yml`
- Coverage Report: `.github/workflows/coverage-report.yml`

### Troubleshooting

**Coverage not generating:**
1. Ensure all dependencies installed (`pytest-cov`, `@vitest/coverage-v8`)
2. Check test execution completes successfully
3. Verify configuration files (`.coveragerc`, `vitest.config.ts`)

**Coverage shows 0% in SonarCloud:**
1. Check path mapping in `sonar-project.properties`
2. Verify coverage file formats (XML for backend, LCOV for frontend)
3. Ensure source paths match between coverage report and SonarCloud config

---

**Last Updated**: {timestamp}
**Next Review**: Quarterly or after major feature releases
"""

        return doc

    def generate(self) -> bool:
        """Generate and save the baseline document."""
        print("📊 Generating coverage baseline documentation...")

        # Ensure docs directory exists
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # Generate document
        doc = self.generate_baseline_document()

        # Write to file
        self.output_file.write_text(doc)
        print(f"✅ Baseline document generated: {self.output_file}")

        # Also generate JSON for CI/CD consumption
        json_output = self.output_file.parent / "coverage-baseline.json"
        baseline_data = {
            "generated": datetime.now().isoformat(),
            "backend_coverage": self.parse_backend_coverage_xml(),
            "frontend_coverage": self.parse_frontend_coverage(),
        }
        json_output.write_text(json.dumps(baseline_data, indent=2))
        print(f"✅ JSON baseline generated: {json_output}")

        return True


def main():
    generator = CoverageBaselineGenerator()

    if not generator.backend_coverage_xml.exists() and not generator.frontend_coverage_summary.exists():
        print("❌ No coverage reports found. Run tests with coverage first:")
        print("   Backend: pytest --cov=services --cov=api --cov-report=xml")
        print("   Frontend: cd frontend && pnpm test:coverage")
        sys.exit(1)

    if generator.generate():
        print("\n✅ Coverage baseline established successfully!")
        print(f"📄 View report: {generator.output_file}")
        sys.exit(0)
    else:
        print("\n❌ Failed to generate coverage baseline")
        sys.exit(1)


if __name__ == "__main__":
    main()
