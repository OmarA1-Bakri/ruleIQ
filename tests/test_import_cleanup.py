"""Unit tests for import cleanup and validation scripts."""

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# Add scripts directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from cleanup_unused_imports import UnusedImportDetector, find_unused_imports, remove_unused_imports
from validate_module_imports import ImportValidator, CircularDependencyDetector


class TestUnusedImportDetector(unittest.TestCase):
    """Test the UnusedImportDetector class."""

    def test_detect_simple_unused_import(self):
        """Test detection of simple unused imports."""
        code = """
import os
import sys

def main():
    print(sys.version)
"""
        tree = ast.parse(code)
        detector = UnusedImportDetector()
        detector.visit(tree)

        unused = detector.get_unused_imports()
        self.assertIn("os", unused)
        self.assertNotIn("sys", unused)

    def test_detect_from_import_unused(self):
        """Test detection of unused from...import statements."""
        code = """
from typing import List, Dict, Optional

def process(items: List[str]) -> Dict[str, int]:
    return {item: len(item) for item in items}
"""
        tree = ast.parse(code)
        detector = UnusedImportDetector()
        detector.visit(tree)

        unused = detector.get_unused_imports()
        self.assertIn("Optional", unused)
        self.assertNotIn("List", unused)
        self.assertNotIn("Dict", unused)

    def test_type_checking_imports_preserved(self):
        """Test that TYPE_CHECKING imports are preserved."""
        code = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mymodule import MyClass

def process(obj):
    # type: (MyClass) -> None
    pass
"""
        tree = ast.parse(code)
        detector = UnusedImportDetector()
        detector.visit(tree)

        unused = detector.get_unused_imports()
        self.assertNotIn("TYPE_CHECKING", unused)
        # MyClass is in TYPE_CHECKING block, shouldn't be marked as unused
        self.assertNotIn("MyClass", unused)

    def test_annotation_imports_preserved(self):
        """Test that imports used in annotations are preserved."""
        code = """
from typing import List, Optional
from datetime import datetime

def get_times() -> List[datetime]:
    return []

def get_value() -> Optional[str]:
    return None
"""
        tree = ast.parse(code)
        detector = UnusedImportDetector()
        detector.visit(tree)

        unused = detector.get_unused_imports()
        self.assertNotIn("List", unused)
        self.assertNotIn("Optional", unused)
        self.assertNotIn("datetime", unused)

    def test_class_base_imports_preserved(self):
        """Test that imports used as base classes are preserved."""
        code = """
from abc import ABC
from collections.abc import Mapping

class MyClass(ABC):
    pass

class MyMapping(Mapping):
    pass
"""
        tree = ast.parse(code)
        detector = UnusedImportDetector()
        detector.visit(tree)

        unused = detector.get_unused_imports()
        self.assertNotIn("ABC", unused)
        self.assertNotIn("Mapping", unused)

    def test_string_annotations(self):
        """Test handling of string annotations."""
        code = """
from typing import List
from mymodule import MyClass

def process() -> "List[MyClass]":
    return []
"""
        tree = ast.parse(code)
        detector = UnusedImportDetector()
        detector.visit(tree)

        unused = detector.get_unused_imports()
        # Both should be detected as used in string annotation
        self.assertNotIn("List", unused)
        self.assertNotIn("MyClass", unused)

    def test_aliased_imports(self):
        """Test detection of aliased imports."""
        code = """
import numpy as np
import pandas as pd

data = np.array([1, 2, 3])
"""
        tree = ast.parse(code)
        detector = UnusedImportDetector()
        detector.visit(tree)

        unused = detector.get_unused_imports()
        self.assertIn("pd", unused)  # Aliased name should be checked
        self.assertNotIn("np", unused)


class TestImportCleaner(unittest.TestCase):
    """Test the import cleaning functions."""

    def test_find_unused_imports_in_file(self):
        """Test finding unused imports in a file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
import os
import sys
from pathlib import Path

print(sys.version)
p = Path('.')
""")
            f.flush()

            try:
                unused, error = find_unused_imports(Path(f.name))
                self.assertIsNone(error)
                self.assertIn("os", unused)
                self.assertNotIn("sys", unused)
                self.assertNotIn("Path", unused)
            finally:
                os.unlink(f.name)

    def test_remove_unused_imports(self):
        """Test removing unused imports from a file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            original_code = """import os
import sys
from pathlib import Path

print(sys.version)
p = Path('.')
"""
            f.write(original_code)
            f.flush()

            try:
                # First find unused imports
                unused, _ = find_unused_imports(Path(f.name))
                self.assertIn("os", unused)

                # Remove them
                modified = remove_unused_imports(Path(f.name), unused)
                self.assertTrue(modified)

                # Check the file was modified correctly
                with open(f.name, "r") as rf:
                    new_code = rf.read()
                    self.assertNotIn("import os", new_code)
                    self.assertIn("import sys", new_code)
                    self.assertIn("from pathlib import Path", new_code)
            finally:
                os.unlink(f.name)

    def test_dry_run_mode(self):
        """Test dry-run mode doesn't modify files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            original_code = """import os
import sys

print(sys.version)
"""
            f.write(original_code)
            f.flush()

            try:
                # Find and "remove" with dry-run
                unused, _ = find_unused_imports(Path(f.name))
                remove_unused_imports(Path(f.name), unused, dry_run=True)

                # Check file wasn't modified
                with open(f.name, "r") as rf:
                    new_code = rf.read()
                    self.assertEqual(original_code, new_code)
            finally:
                os.unlink(f.name)


class TestImportValidator(unittest.TestCase):
    """Test the ImportValidator class."""

    def test_validate_standard_imports(self):
        """Test validation of standard library imports."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
import os
import sys
from pathlib import Path
from typing import List
""")
            f.flush()

            try:
                tree = ast.parse(open(f.name).read())
                validator = ImportValidator(Path(f.name), Path(f.name).parent)
                validator.visit(tree)

                issues = validator.validate_imports()
                # Standard library imports should be valid
                self.assertEqual(len(issues), 0)
            finally:
                os.unlink(f.name)

    def test_validate_all_exports(self):
        """Test validation of __all__ exports."""
        code = """
from typing import List

__all__ = ['function1', 'Class1', 'undefined_export']

def function1():
    pass

class Class1:
    pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            f.flush()

            try:
                tree = ast.parse(code)
                validator = ImportValidator(Path(f.name), Path(f.name).parent)
                validator.visit(tree)

                issues = validator.validate_imports()
                # Should report undefined_export as an issue
                self.assertTrue(any("undefined_export" in issue for issue in issues))
            finally:
                os.unlink(f.name)

    def test_relative_import_resolution(self):
        """Test resolution of relative imports."""
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create package structure
            package_dir = tmpdir_path / "mypackage"
            package_dir.mkdir()
            (package_dir / "__init__.py").touch()

            subpackage_dir = package_dir / "subpackage"
            subpackage_dir.mkdir()
            (subpackage_dir / "__init__.py").touch()

            # Create a module with relative import
            test_file = subpackage_dir / "module.py"
            test_file.write_text("""
from .. import something
from . import other
""")

            tree = ast.parse(test_file.read_text())
            validator = ImportValidator(test_file, tmpdir_path)
            validator.visit(tree)

            # Check that relative imports were resolved correctly
            self.assertEqual(len(validator.from_imports), 2)

            # The first import should resolve to 'mypackage'
            first_import = validator.from_imports[0]
            self.assertEqual(first_import["module"], "mypackage")

            # The second import should resolve to 'mypackage.subpackage'
            second_import = validator.from_imports[1]
            self.assertEqual(second_import["module"], "mypackage.subpackage")


class TestCircularDependencyDetector(unittest.TestCase):
    """Test the CircularDependencyDetector class."""

    def test_detect_simple_circular_dependency(self):
        """Test detection of simple circular dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create two modules that import each other
            module_a = tmpdir_path / "module_a.py"
            module_a.write_text("import module_b\n")

            module_b = tmpdir_path / "module_b.py"
            module_b.write_text("import module_a\n")

            detector = CircularDependencyDetector(tmpdir_path)
            detector.build_import_graph()
            circles = detector.find_circular_dependencies()

            # Should detect one circular dependency
            self.assertEqual(len(circles), 1)
            self.assertIn("module_a", circles[0])
            self.assertIn("module_b", circles[0])

    def test_detect_complex_circular_dependency(self):
        """Test detection of complex circular dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a chain: A -> B -> C -> A
            module_a = tmpdir_path / "module_a.py"
            module_a.write_text("import module_b\n")

            module_b = tmpdir_path / "module_b.py"
            module_b.write_text("import module_c\n")

            module_c = tmpdir_path / "module_c.py"
            module_c.write_text("import module_a\n")

            detector = CircularDependencyDetector(tmpdir_path)
            detector.build_import_graph()
            circles = detector.find_circular_dependencies()

            # Should detect the circular dependency
            self.assertEqual(len(circles), 1)
            circle = circles[0]
            self.assertEqual(len(circle), 3)
            self.assertIn("module_a", circle)
            self.assertIn("module_b", circle)
            self.assertIn("module_c", circle)

    def test_no_circular_dependency(self):
        """Test when there are no circular dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a linear dependency chain: A -> B -> C
            module_a = tmpdir_path / "module_a.py"
            module_a.write_text("import module_b\n")

            module_b = tmpdir_path / "module_b.py"
            module_b.write_text("import module_c\n")

            module_c = tmpdir_path / "module_c.py"
            module_c.write_text("# No imports\n")

            detector = CircularDependencyDetector(tmpdir_path)
            detector.build_import_graph()
            circles = detector.find_circular_dependencies()

            # Should not detect any circular dependencies
            self.assertEqual(len(circles), 0)


if __name__ == "__main__":
    unittest.main()
