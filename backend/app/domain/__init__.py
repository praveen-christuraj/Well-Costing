"""Framework-free domain layer.

Modules in this package hold the business calculation rules. They must not
import FastAPI, SQLAlchemy or Pydantic — the import boundary is enforced by
``tests/unit/test_domain_boundaries.py`` (see ADR-008 and
``docs/testing/strategy.md``). Everything crossing into this layer is a plain
dataclass / Decimal, so the rules can be unit-tested without a database or an
HTTP request.
"""
