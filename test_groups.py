"""Compatibility wrapper for legacy grouped test commands.

Historically the repo referenced `python test_groups.py <group>` from the
Makefile and docs. The file disappeared, which broke those commands. This shim
maps the old group names onto the maintained chunked test runner.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


LEGACY_GROUP_TO_MODE = {
    "all": "full",
    "parallel": "full",
    "group1_unit": "fast",
    "group2_ai_core": "ai",
    "group3_api_basic": "integration",
    "group4_ai_endpoints": "ai",
    "group5_advanced": "ci",
    "group6_e2e": "e2e",
}


def _run_chunked(mode: str) -> int:
    cmd = [
        sys.executable,
        "scripts/run_tests_chunked.py",
        "--mode",
        mode,
    ]
    return subprocess.run(cmd, cwd=Path(__file__).parent).returncode


def _list_groups() -> int:
    print("Legacy test groups:")
    for group, mode in LEGACY_GROUP_TO_MODE.items():
        print(f"  {group:18} -> {mode}")
    print("\nChunked runner modes:")
    return subprocess.run(
        [sys.executable, "scripts/run_tests_chunked.py", "--list-modes"],
        cwd=Path(__file__).parent,
    ).returncode


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python test_groups.py <group>")
        return _list_groups()

    group = argv[1]
    if group == "list":
        return _list_groups()

    mode = LEGACY_GROUP_TO_MODE.get(group)
    if mode is None:
        print(f"Unknown test group: {group}")
        return _list_groups()

    return _run_chunked(mode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
