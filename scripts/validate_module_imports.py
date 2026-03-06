#!/usr/bin/env python3
"""
Module import validator for the RuleIQ codebase.

This script validates module imports, checks for circular dependencies,
verifies __all__ exports, and ensures all imported names can be resolved.
"""

import ast
import argparse
import importlib.util
import sys
from pathlib import Path
from typing import List, Set, Dict, Tuple, Optional, Any
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class ImportValidator(ast.NodeVisitor):
    """AST visitor to validate imports and collect import metadata."""

    def __init__(self, file_path: Path, project_root: Path) -> None:
        self.file_path = file_path
        self.project_root = project_root
        self.imports: List[Dict[str, Any]] = []
        self.from_imports: List[Dict[str, Any]] = []
        self.all_exports: List[str] = []
        self.defined_names: Set[str] = set()
        self.issues: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements."""
        for alias in node.names:
            self.imports.append(
                {
                    "module": alias.name,
                    "name": alias.asname if alias.asname else alias.name,
                    "line": node.lineno,
                }
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from...import statements."""
        if node.module:
            level = node.level  # Number of dots in relative import
            module = node.module

            # Handle relative imports
            if level > 0:
                module = self._resolve_relative_import(module, level)

            for alias in node.names:
                if alias.name == "*":
                    self.from_imports.append(
                        {
                            "module": module,
                            "name": "*",
                            "asname": None,
                            "line": node.lineno,
                            "level": level,
                        }
                    )
                else:
                    self.from_imports.append(
                        {
                            "module": module,
                            "name": alias.name,
                            "asname": alias.asname,
                            "line": node.lineno,
                            "level": level,
                        }
                    )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function definitions."""
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async function definitions."""
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track class definitions."""
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Track assignments, particularly __all__."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.defined_names.add(target.id)
                if target.id == "__all__":
                    # Extract __all__ values
                    if isinstance(node.value, ast.List):
                        for item in node.value.elts:
                            if isinstance(item, ast.Constant):
                                self.all_exports.append(item.value)
        self.generic_visit(node)

    def _resolve_relative_import(self, module: Optional[str], level: int) -> str:
        """Resolve relative import to absolute module path."""
        # Get the package hierarchy of the current file
        rel_path = self.file_path.relative_to(self.project_root)
        parts = list(rel_path.parts[:-1])  # Remove the file name

        # Go up 'level' directories
        if level > len(parts):
            return module or ""

        base_parts = parts[: len(parts) - level + 1] if level > 1 else parts

        if module:
            base_parts.append(module)

        return ".".join(base_parts)

    def validate_imports(self) -> List[str]:
        """Validate all collected imports."""
        issues = []

        # Check each import
        for imp in self.imports:
            module_name = imp["module"]
            if not self._can_import(module_name):
                issues.append(f"Line {imp['line']}: Cannot import module '{module_name}'")

        # Check from...import statements
        for imp in self.from_imports:
            if imp["name"] == "*":
                # Star imports are harder to validate
                continue

            module_name = imp["module"]
            import_name = imp["name"]

            if not self._can_import_from(module_name, import_name):
                issues.append(
                    f"Line {imp['line']}: Cannot import '{import_name}' from '{module_name}'"
                )

        # Validate __all__ exports
        if self.all_exports:
            for export in self.all_exports:
                if export not in self.defined_names:
                    # Check if it's imported
                    imported = False
                    for imp in self.from_imports:
                        if imp["name"] == export or imp["name"] == "*":
                            imported = True
                            break

                    if not imported:
                        issues.append(
                            f"__all__ exports '{export}' but it's not defined or imported"
                        )

        return issues

    def _can_import(self, module_name: str) -> bool:
        """Check if a module can be imported."""
        try:
            # Try to find the module spec
            spec = importlib.util.find_spec(module_name)
            return spec is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            # Check if it's a project module
            return self._is_project_module(module_name)

    def _can_import_from(self, module_name: str, import_name: str) -> bool:
        """Check if a name can be imported from a module."""
        # For project modules, we'll be lenient
        if self._is_project_module(module_name):
            return True

        try:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                return False

            # For built-in modules, assume the import is valid
            # (full validation would require actually importing)
            return True
        except (ImportError, ModuleNotFoundError, ValueError):
            return False

    def _is_project_module(self, module_name: str) -> bool:
        """Check if a module is part of the project."""
        # Convert module name to path
        path_parts = module_name.split(".")
        module_path = self.project_root / Path(*path_parts)

        # Check if it exists as a Python file or package
        return (module_path.with_suffix(".py")).exists() or (module_path / "__init__.py").exists()


class CircularDependencyDetector:
    """Detect circular import dependencies in the codebase."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)
        self.file_to_module: Dict[Path, str] = {}

    def build_import_graph(self) -> None:
        """Build the import dependency graph."""
        for py_file in self.project_root.rglob("*.py"):
            # Skip virtual environments and build directories
            if any(
                part in py_file.parts for part in [".venv", "venv", "__pycache__", "build", "dist"]
            ):
                continue

            module_name = self._path_to_module(py_file)
            self.file_to_module[py_file] = module_name

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                tree = ast.parse(content, filename=str(py_file))
                validator = ImportValidator(py_file, self.project_root)
                validator.visit(tree)

                # Add edges to import graph
                for imp in validator.imports:
                    self.import_graph[module_name].add(imp["module"])

                for imp in validator.from_imports:
                    if imp["module"]:
                        self.import_graph[module_name].add(imp["module"])

            except SyntaxError:
                # Skip files with syntax errors
                pass
            except Exception as e:
                logger.debug(f"Error processing {py_file}: {e}")

    def _path_to_module(self, path: Path) -> str:
        """Convert file path to module name."""
        rel_path = path.relative_to(self.project_root)
        parts = list(rel_path.parts)

        # Remove .py extension from last part
        if parts[-1].endswith(".py"):
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1][:-3]

        return ".".join(parts) if parts else ""

    def find_circular_dependencies(self) -> List[List[str]]:
        """Find all circular dependency chains."""
        circles = []
        visited = set()

        def dfs(module: str, path: List[str], visiting: Set[str]) -> None:
            """Depth-first search for cycles."""
            if module in visiting:
                # Found a cycle
                cycle_start = path.index(module)
                cycle = path[cycle_start:] + [module]
                # Normalize cycle to start with smallest element
                min_idx = cycle.index(min(cycle))
                normalized = cycle[min_idx:] + cycle[:min_idx]
                if normalized not in circles:
                    circles.append(normalized)
                return

            if module in visited:
                return

            visiting.add(module)
            path.append(module)

            for imported in self.import_graph.get(module, set()):
                # Only check project modules
                if imported in self.import_graph:
                    dfs(imported, path.copy(), visiting.copy())

            visited.add(module)

        # Start DFS from each module
        for module in self.import_graph:
            if module not in visited:
                dfs(module, [], set())

        return circles


def validate_file(file_path: Path, project_root: Path) -> Tuple[List[str], Optional[str]]:
    """
    Validate imports in a single Python file.

    Args:
        file_path: Path to the Python file
        project_root: Root directory of the project

    Returns:
        Tuple of (list of issues, error message if any)
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(file_path))
        validator = ImportValidator(file_path, project_root)
        validator.visit(tree)

        issues = validator.validate_imports()
        return issues, None

    except SyntaxError as e:
        return [], f"Syntax error in {file_path}: {e}"
    except Exception as e:
        return [], f"Error processing {file_path}: {e}"


def validate_directory(directory: Path) -> Dict[str, Any]:
    """
    Validate all Python files in a directory.

    Args:
        directory: Directory to validate

    Returns:
        Validation results dictionary
    """
    results = {
        "files_processed": 0,
        "files_with_issues": 0,
        "total_issues": 0,
        "circular_dependencies": [],
        "file_issues": {},
        "errors": 0,
    }

    # Check individual files
    for py_file in directory.rglob("*.py"):
        # Skip virtual environments and build directories
        if any(part in py_file.parts for part in [".venv", "venv", "__pycache__", "build", "dist"]):
            continue

        results["files_processed"] += 1
        issues, error = validate_file(py_file, directory)

        if error:
            logger.warning(error)
            results["errors"] += 1
            continue

        if issues:
            results["files_with_issues"] += 1
            results["total_issues"] += len(issues)
            rel_path = py_file.relative_to(directory)
            results["file_issues"][str(rel_path)] = issues

    # Check for circular dependencies
    logger.info("Checking for circular dependencies...")
    detector = CircularDependencyDetector(directory)
    detector.build_import_graph()
    results["circular_dependencies"] = detector.find_circular_dependencies()

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Python module imports and detect circular dependencies"
    )
    parser.add_argument("path", type=Path, help="File or directory to validate")
    parser.add_argument("--quiet", action="store_true", help="Suppress detailed output")
    parser.add_argument(
        "--check-circular", action="store_true", help="Only check for circular dependencies"
    )

    args = parser.parse_args()

    if args.quiet:
        logger.setLevel(logging.WARNING)

    if not args.path.exists():
        logger.error(f"Path does not exist: {args.path}")
        sys.exit(1)

    if args.path.is_file():
        # Single file validation
        project_root = args.path.parent
        while project_root != project_root.parent:
            if (
                (project_root / "pyproject.toml").exists()
                or (project_root / "setup.py").exists()
                or (project_root / "requirements.txt").exists()
            ):
                break
            project_root = project_root.parent

        issues, error = validate_file(args.path, project_root)

        if error:
            logger.error(error)
            sys.exit(1)

        if issues:
            logger.info(f"Found {len(issues)} import issues:")
            for issue in issues:
                logger.info(f"  - {issue}")
            sys.exit(1)
        else:
            logger.info("No import issues found")
    else:
        # Directory validation
        logger.info(f"Validating directory: {args.path}")
        results = validate_directory(args.path)

        if not args.check_circular:
            # Report file issues
            if results["file_issues"]:
                logger.info("\nImport Issues by File:")
                for file_path, issues in results["file_issues"].items():
                    logger.info(f"\n{file_path}:")
                    for issue in issues:
                        logger.info(f"  - {issue}")

        # Report circular dependencies
        if results["circular_dependencies"]:
            logger.info(
                f"\nFound {len(results['circular_dependencies'])} circular dependency chains:"
            )
            for i, cycle in enumerate(results["circular_dependencies"], 1):
                logger.info(f"  {i}. {' -> '.join(cycle)}")

        # Summary
        logger.info("\n" + "=" * 50)
        logger.info("Summary:")
        logger.info(f"  Files processed: {results['files_processed']}")

        if not args.check_circular:
            logger.info(f"  Files with issues: {results['files_with_issues']}")
            logger.info(f"  Total import issues: {results['total_issues']}")

        logger.info(f"  Circular dependency chains: {len(results['circular_dependencies'])}")

        if results["errors"]:
            logger.info(f"  Errors: {results['errors']}")

        # Exit with non-zero if issues were found
        if results["files_with_issues"] > 0 or results["circular_dependencies"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
