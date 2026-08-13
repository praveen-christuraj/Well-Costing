"""Costing-domain isolation and placeholder tests."""

import ast
from pathlib import Path

import pytest
from app.domain.costing.calculations import calculate_estimate
from app.domain.costing.contingency import apply_contingency
from app.domain.costing.escalation import apply_escalation
from app.domain.costing.quantity_engine import resolve_quantity
from app.domain.costing.rate_engine import resolve_rate
from app.domain.costing.totals import calculate_totals

FORBIDDEN_ROOTS = {"fastapi", "sqlalchemy", "pydantic"}
DOMAIN_ROOT = Path(__file__).parents[2] / "app" / "domain"


def test_domain_has_no_framework_imports() -> None:
    violations: list[str] = []
    for path in DOMAIN_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.split(".", maxsplit=1)[0] in FORBIDDEN_ROOTS:
                    violations.append(f"{path.name}:{node.lineno}:{name}")
    assert violations == []


@pytest.mark.parametrize(
    "placeholder",
    [
        calculate_estimate,
        resolve_rate,
        resolve_quantity,
        apply_contingency,
        apply_escalation,
        calculate_totals,
    ],
)
def test_unconfirmed_costing_rules_fail_loudly(placeholder: object) -> None:
    callable_placeholder = placeholder
    with pytest.raises(
        NotImplementedError,
        match="Business rule to be confirmed during Excel/business-rule discovery",
    ):
        callable_placeholder(object())  # type: ignore[operator]
