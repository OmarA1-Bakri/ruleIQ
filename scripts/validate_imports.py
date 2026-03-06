#!/usr/bin/env python3
"""
Script to validate Python import statements across the codebase.
Detects missing modules, circular imports, and other import issues.
"""

import ast
import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict, Set, Optional
import importlib.util
import json


class ImportValidator:
    """Validates import statements in Python files."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.import_graph = {}  # file -> set of imported files
        self.external_imports = set()  # third-party packages
        self.missing_imports = []  # imports that couldn't be resolved
        self.circular_imports = []  # detected circular import chains
        self.unused_imports = []  # imports that aren't used

    def scan_directory(self, path: Path) -> List[Path]:
        """Scan directory for Python files."""
        python_files = []

        for root, dirs, files in os.walk(path):
            # Skip common directories
            dirs[:] = [
                d
                for d in dirs
                if d
                not in {".venv", "venv", "__pycache__", ".git", "node_modules", ".pytest_cache"}
            ]

            for file in files:
                if file.endswith(".py"):
                    python_files.append(Path(root) / file)

        return python_files

    def parse_imports(self, filepath: Path) -> Dict[str, any]:
        """Parse all imports from a Python file."""
        result = {
            "file": str(filepath.relative_to(self.project_root)),
            "imports": [],
            "from_imports": [],
            "errors": [],
        }

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)

            # Track which imports are actually used
            used_names = set()

            for node in ast.walk(tree):
                # Collect Import statements
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        import_info = {
                            "module": alias.name,
                            "alias": alias.asname,
                            "line": node.lineno,
                        }
                        result["imports"].append(import_info)

                # Collect ImportFrom statements
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for alias in node.names:
                            from_import_info = {
                                "module": node.module,
                                "name": alias.name,
                                "alias": alias.asname,
                                "level": node.level,  # relative import level
                                "line": node.lineno,
                            }
                            result["from_imports"].append(from_import_info)

                # Track name usage
                elif isinstance(node, ast.Name):
                    used_names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        used_names.add(node.value.id)

            # Check for unused imports
            for imp in result["imports"]:
                name = imp["alias"] or imp["module"].split(".")[0]
                if name not in used_names:
                    self.unused_imports.append(
                        {"file": result["file"], "import": imp["module"], "line": imp["line"]}
                    )

            for imp in result["from_imports"]:
                name = imp["alias"] or imp["name"]
                if name not in used_names and name != "*":
                    self.unused_imports.append(
                        {
                            "file": result["file"],
                            "import": f"{imp['module']}.{imp['name']}",
                            "line": imp["line"],
                        }
                    )

        except SyntaxError as e:
            result["errors"].append(f"Syntax error: {e}")
        except Exception as e:
            result["errors"].append(f"Error parsing file: {e}")

        return result

    def resolve_import(self, module_name: str, from_file: Path) -> Optional[Path]:
        """Try to resolve an import to a file path."""
        # Handle relative imports
        if module_name.startswith("."):
            # Relative import - resolve based on current file location
            current_package = from_file.parent
            level = len(module_name) - len(module_name.lstrip("."))

            for _ in range(level - 1):
                current_package = current_package.parent

            if module_name.strip("."):
                module_path = module_name.strip(".").replace(".", "/")
                potential_paths = [
                    current_package / f"{module_path}.py",
                    current_package / module_path / "__init__.py",
                ]
            else:
                potential_paths = [current_package / "__init__.py"]
        else:
            # Absolute import
            module_path = module_name.replace(".", "/")
            potential_paths = [
                self.project_root / f"{module_path}.py",
                self.project_root / module_path / "__init__.py",
            ]

        for path in potential_paths:
            if path.exists():
                return path

        return None

    def check_module_exists(self, module_name: str) -> bool:
        """Check if a module exists (either local or installed)."""
        # First check if it's a built-in or installed module
        spec = importlib.util.find_spec(module_name.split(".")[0])
        if spec is not None:
            return True

        # Check if it's a local module
        module_path = module_name.replace(".", "/")
        potential_paths = [
            self.project_root / f"{module_path}.py",
            self.project_root / module_path / "__init__.py",
        ]

        return any(p.exists() for p in potential_paths)

    def build_import_graph(self, files: List[Path]):
        """Build a graph of import dependencies."""
        for filepath in files:
            relative_path = filepath.relative_to(self.project_root)
            self.import_graph[str(relative_path)] = set()

            import_data = self.parse_imports(filepath)

            # Process regular imports
            for imp in import_data["imports"]:
                resolved = self.resolve_import(imp["module"], filepath)
                if resolved:
                    self.import_graph[str(relative_path)].add(
                        str(resolved.relative_to(self.project_root))
                    )
                elif not self.check_module_exists(imp["module"]):
                    self.missing_imports.append(
                        {"file": str(relative_path), "module": imp["module"], "line": imp["line"]}
                    )
                else:
                    self.external_imports.add(imp["module"].split(".")[0])

            # Process from imports
            for imp in import_data["from_imports"]:
                if imp["module"]:
                    resolved = self.resolve_import(imp["module"], filepath)
                    if resolved:
                        self.import_graph[str(relative_path)].add(
                            str(resolved.relative_to(self.project_root))
                        )
                    elif not self.check_module_exists(imp["module"]):
                        self.missing_imports.append(
                            {
                                "file": str(relative_path),
                                "module": imp["module"],
                                "name": imp["name"],
                                "line": imp["line"],
                            }
                        )
                    else:
                        self.external_imports.add(imp["module"].split(".")[0])

    def detect_circular_imports(self):
        """Detect circular import dependencies."""

        def find_cycles(node: str, path: List[str], visited: Set[str]):
            if node in path:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                self.circular_imports.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            path.append(node)

            for neighbor in self.import_graph.get(node, set()):
                find_cycles(neighbor, path[:], visited)

        visited = set()
        for node in self.import_graph:
            if node not in visited:
                find_cycles(node, [], visited)

        # Remove duplicate cycles
        unique_cycles = []
        for cycle in self.circular_imports:
            # Normalize cycle (start with smallest element)
            min_idx = cycle.index(min(cycle))
            normalized = cycle[min_idx:] + cycle[:min_idx]
            if normalized not in unique_cycles:
                unique_cycles.append(normalized)

        self.circular_imports = unique_cycles

    def validate_all(self, files: List[Path]) -> Dict:
        """Run all validation checks."""
        print(f"Validating imports in {len(files)} files...")

        # Build import graph
        self.build_import_graph(files)

        # Detect circular imports
        self.detect_circular_imports()

        # Compile results
        results = {
            "total_files": len(files),
            "external_packages": sorted(list(self.external_imports)),
            "missing_imports": self.missing_imports,
            "circular_imports": self.circular_imports,
            "unused_imports": self.unused_imports,
            "statistics": {
                "total_missing": len(self.missing_imports),
                "total_circular": len(self.circular_imports),
                "total_unused": len(self.unused_imports),
                "total_external": len(self.external_imports),
            },
        }

        return results

    def print_report(self, results: Dict, verbose: bool = False):
        """Print validation report."""
        print("\n" + "=" * 60)
        print("IMPORT VALIDATION REPORT")
        print("=" * 60)

        stats = results["statistics"]
        print(f"\nFiles analyzed: {results['total_files']}")
        print(f"External packages used: {stats['total_external']}")
        print(f"Missing imports: {stats['total_missing']}")
        print(f"Circular import chains: {stats['total_circular']}")
        print(f"Unused imports: {stats['total_unused']}")

        # Show missing imports
        if results["missing_imports"]:
            print("\n❌ MISSING IMPORTS:")
            for item in results["missing_imports"][:10]:
                if "name" in item:
                    print(
                        f"  {item['file']}:{item['line']} - Cannot import '{item['name']}' from '{item['module']}'"
                    )
                else:
                    print(
                        f"  {item['file']}:{item['line']} - Cannot import module '{item['module']}'"
                    )

            if len(results["missing_imports"]) > 10:
                print(f"  ... and {len(results['missing_imports']) - 10} more")

        # Show circular imports
        if results["circular_imports"]:
            print("\n🔄 CIRCULAR IMPORTS:")
            for cycle in results["circular_imports"][:5]:
                chain = " -> ".join(cycle)
                print(f"  {chain}")

            if len(results["circular_imports"]) > 5:
                print(f"  ... and {len(results['circular_imports']) - 5} more")

        # Show unused imports in verbose mode
        if verbose and results["unused_imports"]:
            print("\n⚠️  UNUSED IMPORTS:")
            for item in results["unused_imports"][:10]:
                print(f"  {item['file']}:{item['line']} - Unused import '{item['import']}'")

            if len(results["unused_imports"]) > 10:
                print(f"  ... and {len(results['unused_imports']) - 10} more")

        # Show external packages
        if verbose:
            print("\n📦 EXTERNAL PACKAGES:")
            for pkg in results["external_packages"][:20]:
                print(f"  - {pkg}")

            if len(results["external_packages"]) > 20:
                print(f"  ... and {len(results['external_packages']) - 20} more")


def main():
    parser = argparse.ArgumentParser(description="Validate Python imports")
    parser.add_argument(
        "path", nargs="?", default=".", help="Path to scan (default: current directory)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--fix-unused",
        action="store_true",
        help="Automatically remove unused imports (experimental)",
    )
    parser.add_argument(
        "--ci", action="store_true", help="CI mode - exit with error if issues found"
    )

    args = parser.parse_args()

    project_root = Path(args.path).resolve()
    if not project_root.exists():
        print(f"Error: Path {project_root} not found")
        sys.exit(1)

    validator = ImportValidator(project_root)

    # Scan for Python files
    files = validator.scan_directory(project_root)
    print(f"Found {len(files)} Python files")

    # Run validation
    results = validator.validate_all(files)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        validator.print_report(results, verbose=args.verbose)

    # CI mode exit codes
    if args.ci:
        if results["missing_imports"] or results["circular_imports"]:
            print("\n❌ CI Check Failed: Import issues detected")
            sys.exit(1)
        else:
            print("\n✅ CI Check Passed: No critical import issues")
            sys.exit(0)


if __name__ == "__main__":
    main()
