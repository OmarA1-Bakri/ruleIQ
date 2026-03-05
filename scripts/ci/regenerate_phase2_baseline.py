#!/usr/bin/env python3
"""Regenerate PHASE2 baseline metrics used by CI trend tracking.

This script updates docs/PHASE2_BASELINE.txt, with emphasis on separating:
- RUFF_ERRORS
- RUFF_SUPPRESSED
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "docs" / "PHASE2_BASELINE.txt"
RUFF_CONFIG = ROOT / "ruff.toml"


def _parse_baseline(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return lines, values


def _get_ruff_errors() -> int:
    try:
        result = subprocess.run(
            ["ruff", "check", str(ROOT), "--statistics"],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        )
    except FileNotFoundError:
        return -1

    total = 0
    pattern = re.compile(r"^\s*(\d+)\s+")
    output = result.stdout or ""
    for raw_line in output.splitlines():
        match = pattern.match(raw_line)
        if match:
            total += int(match.group(1))
    return total


def _get_ruff_suppressed() -> int:
    config = tomllib.loads(RUFF_CONFIG.read_text(encoding="utf-8"))
    lint = config.get("lint", {})
    ignore = lint.get("ignore", [])
    return len(ignore)


def _render(lines: list[str], values: dict[str, str]) -> str:
    output: list[str] = []
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        output.append(f"{key}={values.get(key, line.split('=', 1)[1].strip())}")
    if "RUFF_SUPPRESSED" not in values:
        output.append(f"RUFF_SUPPRESSED={values.get('RUFF_SUPPRESSED', '0')}")
    return "\n".join(output) + "\n"


def main() -> int:
    lines, values = _parse_baseline(BASELINE_PATH)

    ruff_errors = _get_ruff_errors()
    if ruff_errors >= 0:
        values["RUFF_ERRORS"] = str(ruff_errors)

    values["RUFF_SUPPRESSED"] = str(_get_ruff_suppressed())

    BASELINE_PATH.write_text(_render(lines, values), encoding="utf-8")
    print(f"Updated {BASELINE_PATH}")
    print(f"RUFF_ERRORS={values.get('RUFF_ERRORS')}")
    print(f"RUFF_SUPPRESSED={values.get('RUFF_SUPPRESSED')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
