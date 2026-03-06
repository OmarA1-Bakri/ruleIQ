import ast
import pathlib
import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDES = {".venv", "venv", "__pycache__", ".git", "node_modules", ".pytest_cache"}


@pytest.mark.parametrize(
    "path", [p for p in PROJECT_ROOT.rglob("*.py") if not any(part in EXCLUDES for part in p.parts)]
)
def test_all_python_files_parse(path):
    source = path.read_text(encoding="utf-8")
    ast.parse(source)
