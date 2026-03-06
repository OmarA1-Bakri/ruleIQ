#!/usr/bin/env python3
"""Lightweight repository secret scan.

Heuristics intentionally cover the formats previously leaked in the repository
(Stack, Neon, OpenAI, Google API keys, JWTs, etc.).  The script processes tracked
files only and fails the run when suspicious tokens are detected.
"""

import math
import re
import subprocess
from pathlib import Path
from typing import Iterable, List, Tuple

# Detect default password/secret parameters in os.getenv() calls
# These are dangerous because they allow code to run with insecure defaults
RE_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("stack-key", re.compile(r"pck_[A-Za-z0-9]{10,}")),
    ("stack-secret", re.compile(r"ssk_[A-Za-z0-9]{10,}")),
    ("openai-key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}")),
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z-_]{20,}")),
    ("neon-connection", re.compile(r"npg_[A-Za-z0-9]{8,}")),
    ("jwt", re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")),
    (
        "generic-secret",
        re.compile(
            r"(?i)(?:secret|api_key|token|password)\s*[:=]\s*['\"][A-Za-z0-9+/=_-]{16,}['\"]"
        ),
    ),
    (
        "default-password-param",
        re.compile(
            r"os\.getenv\([^)]*,\s*['\"](?:password|secret|key|token|credential)[^'\"]*['\"]",
            re.IGNORECASE,
        ),
    ),
    (
        "neo4j-default-password",
        re.compile(r"os\.getenv\(['\"]NEO4J_PASSWORD['\"],\s*['\"][^'\"]+['\"]"),
    ),
)

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".zip",
    ".gz",
    ".tgz",
    ".ico",
    ".jar",
    ".mp4",
    ".mov",
}

MAX_FILE_SIZE = 512 * 1024  # 512 KB

SKIP_DIRS = {
    ".git",
    ".scannerwork",
    ".claude",
    "node_modules",
    "logs",
    "__pycache__",
}

GENERIC_PLACEHOLDER_SNIPPETS = (
    "mock",
    "dummy",
    "placeholder",
    "example",
    "sample",
    "changeme",
    "fake",
    "access-token",
    "refresh-token",
    "new-access",
    "new-token",
)


def shannon_entropy(candidate: str) -> float:
    distribution = {c: candidate.count(c) for c in set(candidate)}
    length = len(candidate)
    return -sum(count / length * math.log2(count / length) for count in distribution.values())


def high_entropy_strings(content: str) -> Iterable[str]:
    for token in re.findall(r"[A-Za-z0-9+/=_-]{32,}", content):
        if token.replace("_", "").replace("-", "").isalnum() and token.upper() == token:
            continue  # likely a constant name such as JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        if token.startswith("<") and token.endswith(">"):
            continue  # placeholder value
        if not any(ch.islower() for ch in token) or not any(ch.isdigit() for ch in token):
            continue
        if shannon_entropy(token) >= 4.0:
            yield token


def is_textual(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return False
    if path.stat().st_size > MAX_FILE_SIZE:
        return False
    try:
        with path.open("rb") as handle:
            chunk = handle.read(4096)
        chunk.decode("utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def tracked_files() -> List[Path]:
    result = subprocess.run(["git", "ls-files"], check=True, capture_output=True, text=True)
    candidates: List[Path] = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        path = Path(line)
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        candidates.append(path)
    return candidates


def should_ignore_match(match_name: str, token: str, path: Path) -> bool:
    """Return True when a match clearly represents a benign placeholder."""

    lowered = token.lower()
    value_match = re.search(r"['\"]([^'\"]+)['\"]", token)
    value = value_match.group(1) if value_match else token
    lowered_value = value.lower()

    if match_name == "openai-key" and "risk-management-framework" in lowered:
        return True

    if match_name == "generic-secret":
        if len(value) < 20 and not any(ch.isdigit() for ch in value):
            return True
        if any(snippet in lowered_value for snippet in GENERIC_PLACEHOLDER_SNIPPETS):
            return True
        if value.endswith("_secret") and not any(ch.isdigit() for ch in value):
            return True
        if "frontend" in path.parts and "tests" in path.parts:
            if "token" in lowered_value and not any(ch.isdigit() for ch in value):
                return True

    if match_name in ("default-password-param", "neo4j-default-password"):
        # Check if this is in a test file
        if "tests" in path.parts or "test_" in path.name:
            return True
        # Check if the default value is obviously a placeholder
        if any(
            snippet in lowered_value for snippet in ("test", "mock", "dummy", "example", "changeme")
        ):
            return True
        # Otherwise, this is a real violation
        return False

    return False


def scan_file(path: Path) -> List[Tuple[str, str]]:
    findings: List[Tuple[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings

    for name, pattern in RE_PATTERNS:
        for match in pattern.findall(text):
            token = str(match)
            if should_ignore_match(name, token, path):
                continue
            findings.append((name, token))

        # Optional entropy-based detection disabled for now to reduce noise.

    return findings


def main() -> None:
    suspicious: List[Tuple[str, Path, str]] = []
    for file_path in tracked_files():
        if not file_path.exists() or not is_textual(file_path):
            continue
        for kind, token in scan_file(file_path):
            suspicious.append((kind, file_path, token[:80]))

    if suspicious:
        print("Potential secrets detected:\n")
        for kind, path, token in suspicious:
            print(f"- {kind}: {path} :: {token}")
            if kind in ("default-password-param", "neo4j-default-password"):
                print("  ⚠️  CRITICAL: Default password parameter detected!")
                print("     Remove the default value and require the environment variable.")
        print("\nIf this is a false positive, add an allowlist to the scanner or redact the value.")
        raise SystemExit(1)

    print("No secrets detected.")


if __name__ == "__main__":
    main()
