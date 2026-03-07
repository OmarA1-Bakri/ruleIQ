#!/usr/bin/env python3
"""
Validate type annotations in Python source files.

This script checks:
1. Special methods have return annotations
2. Class/static methods have return annotations
3. Variadic arguments (*args, **kwargs) are typed (Any)
"""

import ast
import sys
from pathlib import Path
from typing import List, Set


def is_special_method(name: str) -> bool:
    """Check if method is a special/dunder method."""
    special_methods = {
        "__init__",
        "__aenter__",
        "__aexit__",
        "__enter__",
        "__exit__",
        "__call__",
        "__str__",
        "__repr__",
        "__eq__",
        "__ne__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__hash__",
        "__bool__",
        "__len__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
        "__contains__",
        "__iter__",
        "__next__",
        "__reversed__",
        "__getattr__",
        "__setattr__",
        "__delattr__",
        "__dir__",
        "__class__",
        "__new__",
        "__del__",
        "__bytes__",
        "__format__",
        "__sizeof__",
        "__reduce__",
        "__reduce_ex__",
        "__getstate__",
        "__setstate__",
        "__copy__",
        "__deepcopy__",
        "__await__",
        "__aiter__",
        "__anext__",
        "__round__",
        "__trunc__",
        "__floor__",
        "__ceil__",
        "__abs__",
        "__pos__",
        "__neg__",
        "__invert__",
    }
    return name in special_methods


def check_function_annotations(node: ast.FunctionDef, filepath: str, violations: List[str]) -> None:
    """Check function/method annotations."""
    # Check if it's a special method that needs return annotation
    if is_special_method(node.name) and node.returns is None:
        violations.append(
            f"{filepath}:{node.lineno}: Special method '{node.name}' missing return annotation"
        )

    # Check if it's a classmethod or staticmethod
    is_classmethod = any(
        isinstance(dec, ast.Name) and dec.id == "classmethod" for dec in node.decorator_list
    )
    is_staticmethod = any(
        isinstance(dec, ast.Name) and dec.id == "staticmethod" for dec in node.decorator_list
    )

    if (is_classmethod or is_staticmethod) and node.returns is None:
        method_type = "classmethod" if is_classmethod else "staticmethod"
        violations.append(
            f"{filepath}:{node.lineno}: {method_type} '{node.name}' missing return annotation"
        )

    # Check variadic arguments
    if node.args.vararg and node.args.vararg.annotation is None:
        violations.append(f"{filepath}:{node.lineno}: Function '{node.name}' has untyped *args")

    if node.args.kwarg and node.args.kwarg.annotation is None:
        violations.append(f"{filepath}:{node.lineno}: Function '{node.name}' has untyped **kwargs")


def validate_file(filepath: Path) -> List[str]:
    """Validate type annotations in a Python file."""
    violations = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(filepath))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                check_function_annotations(node, str(filepath), violations)

    except SyntaxError as e:
        violations.append(f"{filepath}: Syntax error - {e}")
    except Exception as e:
        violations.append(f"{filepath}: Error parsing file - {e}")

    return violations


def find_python_files(root_dir: Path, exclude_dirs: Set[str] = None) -> List[Path]:
    """Find all Python files in directory, excluding certain directories."""
    if exclude_dirs is None:
        exclude_dirs = {".venv", "venv", "__pycache__", ".git", "node_modules", "build", "dist"}

    python_files = []
    for path in root_dir.rglob("*.py"):
        # Skip files in excluded directories
        if any(excluded in path.parts for excluded in exclude_dirs):
            continue
        python_files.append(path)

    return python_files


def main() -> int:
    """Main entry point."""
    # Target files to check based on the comments
    target_files = [
        "api/clients/base_api_client.py",
        "api/clients/aws_client.py",
        "api/clients/google_workspace_client.py",
        "services/caching/cache_manager.py",
    ]

    # If specific files are provided as arguments, use those
    if len(sys.argv) > 1:
        target_files = sys.argv[1:]

    violations = []
    files_checked = 0

    for filepath_str in target_files:
        filepath = Path(filepath_str)
        if filepath.exists() and filepath.is_file():
            file_violations = validate_file(filepath)
            violations.extend(file_violations)
            files_checked += 1
            if not file_violations:
                print(f"✓ {filepath}: No violations")
        else:
            print(f"⚠ {filepath}: File not found or not a file")

    # Print summary
    print(f"\n{'=' * 60}")
    print("Type Annotation Validation Summary")
    print(f"{'=' * 60}")
    print(f"Files checked: {files_checked}")
    print(f"Violations found: {len(violations)}")

    if violations:
        print("\nViolations:")
        for violation in violations:
            print(f"  ❌ {violation}")
        return 1
    else:
        print("\n✅ All type annotations are correct!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
