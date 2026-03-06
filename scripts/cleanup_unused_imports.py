#!/usr/bin/env python3
"""
AST-based unused import detector and fixer for the RuleIQ codebase.

This script uses AST parsing to detect and optionally remove unused imports,
respecting TYPE_CHECKING blocks and type annotations.
"""

import ast
import argparse
import sys
from pathlib import Path
from typing import List, Set, Dict, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class UnusedImportDetector(ast.NodeVisitor):
    """AST visitor to detect unused imports in Python code."""

    def __init__(self) -> None:
        self.imports: Dict[str, ast.ImportFrom | ast.Import] = {}
        self.used_names: Set[str] = set()
        self.in_type_checking = False
        self.type_checking_imports: Set[str] = set()
        self.annotations: Set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements."""
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            if self.in_type_checking:
                self.type_checking_imports.add(name)
            else:
                self.imports[name] = node
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from...import statements."""
        if node.module == "__future__":
            # Never remove __future__ imports
            self.generic_visit(node)
            return

        for alias in node.names:
            if alias.name == "*":
                # Skip star imports for now
                continue
            name = alias.asname if alias.asname else alias.name
            if self.in_type_checking:
                self.type_checking_imports.add(name)
            else:
                self.imports[name] = node
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Track TYPE_CHECKING blocks."""
        # Check if this is a TYPE_CHECKING block
        if (isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING") or (
            isinstance(node.test, ast.Attribute)
            and isinstance(node.test.value, ast.Name)
            and node.test.value.id == "typing"
            and node.test.attr == "TYPE_CHECKING"
        ):
            old_state = self.in_type_checking
            self.in_type_checking = True
            for stmt in node.body:
                self.visit(stmt)
            self.in_type_checking = old_state
            for stmt in node.orelse:
                self.visit(stmt)
        else:
            self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Track name usage."""
        if not isinstance(node.ctx, ast.Store):
            self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Track attribute access."""
        if isinstance(node.value, ast.Name):
            self.used_names.add(node.value.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function definitions and annotations."""
        # Process return annotation
        if node.returns:
            self._extract_annotation_names(node.returns)

        # Process argument annotations
        for arg in node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                self._extract_annotation_names(arg.annotation)

        # Process vararg and kwarg annotations
        if node.args.vararg and node.args.vararg.annotation:
            self._extract_annotation_names(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation:
            self._extract_annotation_names(node.args.kwarg.annotation)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async function definitions."""
        self.visit_FunctionDef(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Track annotated assignments."""
        if node.annotation:
            self._extract_annotation_names(node.annotation)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track class definitions and base classes."""
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.used_names.add(base.id)
            elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                self.used_names.add(base.value.id)
        self.generic_visit(node)

    def _extract_annotation_names(self, annotation) -> None:
        """Extract names used in type annotations."""
        if isinstance(annotation, ast.Name):
            self.annotations.add(annotation.id)
        elif isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            # String annotations
            try:
                parsed = ast.parse(annotation.value, mode="eval")
                self._extract_annotation_names(parsed.body)
            except:
                # If we can't parse it, extract simple names
                import re

                names = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", annotation.value)
                self.annotations.update(names)
        elif isinstance(annotation, ast.Subscript):
            self._extract_annotation_names(annotation.value)
            self._extract_annotation_names(annotation.slice)
        elif isinstance(annotation, ast.Attribute):
            if isinstance(annotation.value, ast.Name):
                self.annotations.add(annotation.value.id)
        elif hasattr(annotation, "_fields"):
            # Recursively process composite annotations
            for field in annotation._fields:
                value = getattr(annotation, field, None)
                if value:
                    if isinstance(value, list):
                        for item in value:
                            self._extract_annotation_names(item)
                    else:
                        self._extract_annotation_names(value)

    def get_unused_imports(self) -> List[str]:
        """Get list of unused import names."""
        all_used = self.used_names | self.annotations | self.type_checking_imports
        unused = []
        for name, _node in self.imports.items():
            if name not in all_used:
                # Check if it's used in __all__
                if name not in self.used_names:
                    unused.append(name)
        return unused


def find_unused_imports(file_path: Path) -> Tuple[List[str], Optional[str]]:
    """
    Find unused imports in a Python file.

    Args:
        file_path: Path to the Python file

    Returns:
        Tuple of (list of unused import names, error message if any)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(file_path))
        detector = UnusedImportDetector()
        detector.visit(tree)

        return detector.get_unused_imports(), None
    except SyntaxError as e:
        return [], f"Syntax error in {file_path}: {e}"
    except Exception as e:
        return [], f"Error processing {file_path}: {e}"


def remove_unused_imports(file_path: Path, unused: List[str], dry_run: bool = False) -> bool:
    """
    Remove unused imports from a Python file.

    Args:
        file_path: Path to the Python file
        unused: List of unused import names
        dry_run: If True, don't actually modify the file

    Returns:
        True if file was modified (or would be in dry-run mode)
    """
    if not unused:
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        modified_lines = []
        imports_removed = set()

        for line in lines:
            # Simple heuristic - can be improved with AST rewriting
            should_keep = True
            stripped = line.strip()

            if stripped.startswith(("import ", "from ")):
                for name in unused:
                    # Check various import patterns
                    patterns = [
                        f"import {name}",
                        f"import {name} as",
                        f"from .* import {name}",
                        f"from .* import .*, {name}",
                        f"from .* import {name},",
                        f"import {name},",
                    ]

                    import re

                    for pattern in patterns:
                        if re.search(pattern, line):
                            should_keep = False
                            imports_removed.add(name)
                            logger.info(f"  Removing: {stripped}")
                            break

                    if not should_keep:
                        break

            if should_keep:
                modified_lines.append(line)

        if imports_removed:
            if not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(modified_lines)
                logger.info(f"  Removed {len(imports_removed)} unused imports from {file_path}")
            else:
                logger.info(
                    f"  Would remove {len(imports_removed)} unused imports from {file_path}"
                )
            return True

        return False

    except Exception as e:
        logger.error(f"Error removing imports from {file_path}: {e}")
        return False


def process_directory(directory: Path, dry_run: bool = False, fix: bool = False) -> Dict[str, int]:
    """
    Process all Python files in a directory.

    Args:
        directory: Directory to process
        dry_run: If True, don't modify files
        fix: If True, remove unused imports

    Returns:
        Statistics dictionary
    """
    stats = {
        "files_processed": 0,
        "files_with_unused": 0,
        "total_unused": 0,
        "files_fixed": 0,
        "errors": 0,
    }

    for py_file in directory.rglob("*.py"):
        # Skip virtual environments and build directories
        if any(part in py_file.parts for part in [".venv", "venv", "__pycache__", "build", "dist"]):
            continue

        stats["files_processed"] += 1
        unused, error = find_unused_imports(py_file)

        if error:
            logger.warning(error)
            stats["errors"] += 1
            continue

        if unused:
            stats["files_with_unused"] += 1
            stats["total_unused"] += len(unused)

            rel_path = py_file.relative_to(directory)
            logger.info(f"\n{rel_path}: {len(unused)} unused imports")
            for name in unused:
                logger.info(f"  - {name}")

            if fix and remove_unused_imports(py_file, unused, dry_run):
                stats["files_fixed"] += 1

    return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Detect and remove unused imports in Python code")
    parser.add_argument("path", type=Path, help="File or directory to process")
    parser.add_argument(
        "--fix", action="store_true", help="Remove unused imports (default is to only report)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be changed without modifying files"
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress detailed output")

    args = parser.parse_args()

    if args.quiet:
        logger.setLevel(logging.WARNING)

    if not args.path.exists():
        logger.error(f"Path does not exist: {args.path}")
        sys.exit(1)

    if args.path.is_file():
        unused, error = find_unused_imports(args.path)
        if error:
            logger.error(error)
            sys.exit(1)

        if unused:
            logger.info(f"Found {len(unused)} unused imports:")
            for name in unused:
                logger.info(f"  - {name}")

            if args.fix:
                remove_unused_imports(args.path, unused, args.dry_run)
        else:
            logger.info("No unused imports found")
    else:
        logger.info(f"Processing directory: {args.path}")
        stats = process_directory(args.path, args.dry_run, args.fix)

        logger.info("\n" + "=" * 50)
        logger.info("Summary:")
        logger.info(f"  Files processed: {stats['files_processed']}")
        logger.info(f"  Files with unused imports: {stats['files_with_unused']}")
        logger.info(f"  Total unused imports: {stats['total_unused']}")
        if args.fix:
            logger.info(f"  Files fixed: {stats['files_fixed']}")
        if stats["errors"]:
            logger.info(f"  Errors: {stats['errors']}")

        # Exit with non-zero if unused imports were found and not fixed
        if stats["files_with_unused"] > 0 and not args.fix:
            sys.exit(1)


if __name__ == "__main__":
    main()
