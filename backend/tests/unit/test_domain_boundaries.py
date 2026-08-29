"""Import-boundary test for the framework-free domain package.

ADR-008 requires a rebuilt domain package to stay free of FastAPI, SQLAlchemy
and Pydantic so the calculation rules remain unit-testable without a database
or an HTTP request. This walks every module under ``app/domain`` with the AST
parser and fails on any forbidden import — including imports nested inside
functions.
"""

import ast
from pathlib import Path

import pytest

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "app" / "domain"
FORBIDDEN_ROOTS = {"fastapi", "sqlalchemy", "pydantic", "starlette"}


def domain_modules() -> list[Path]:
    return sorted(path for path in DOMAIN_DIR.rglob("*.py") if path.name != "__init__.py")


def imported_roots(source: str) -> set[str]:
    roots: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        # Absolute ImportFrom only: relative imports (level > 0) stay inside
        # the package and cannot pull a framework in.
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_domain_package_exists_with_a_calculation_module() -> None:
    assert DOMAIN_DIR.is_dir(), "app/domain must exist (ADR-008)"
    assert (DOMAIN_DIR / "afe_costing.py").is_file()


@pytest.mark.parametrize("module_path", domain_modules(), ids=lambda path: path.name)
def test_domain_module_has_no_framework_imports(module_path: Path) -> None:
    offending = imported_roots(module_path.read_text()) & FORBIDDEN_ROOTS
    assert not offending, (
        f"{module_path.name} imports framework packages {sorted(offending)}; "
        "the domain layer must stay framework-free"
    )
