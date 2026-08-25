"""Schema drift detection and development auto-migration.

Two responsibilities:

* ``auto_upgrade_head`` applies pending Alembic migrations when the backend
  boots in a *local* environment (``development`` / ``termux``). Local
  databases are exactly the ones that silently fall behind when the code is
  pulled and the servers are restarted, which is the classic cause of
  mysterious HTTP 500s on every list endpoint. Hosted environments apply
  migrations during the build instead, so this stays off there.

* ``detect_schema_drift`` compares the live database against what the
  application expects (alembic head revision plus a small set of critical
  tables/columns) and returns a human-readable explanation. The health
  endpoints surface it, and the global exception handler translates
  missing-table/column database errors into an actionable 503 instead of a
  generic 500.
"""

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.alembic_url import escape_for_alembic

logger = logging.getLogger("app")

BACKEND_DIR = Path(__file__).resolve().parents[2]  # app/db/schema.py -> backend/
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
ALEMBIC_SCRIPTS = BACKEND_DIR / "alembic"

# The active source chain. If any table/column is missing, planning, Daily
# Cost, Cost Control and reporting cannot remain traceable.
CRITICAL_SCHEMA: dict[str, tuple[str, ...]] = {
    "projects": ("code", "name", "is_active"),
    "wells": ("code", "name", "status", "rates_locked_at", "rate_lock_reference"),
    "afes": (
        "well_id",
        "code",
        "title",
        "status",
        "revision_number",
        "budget_amount",
        "total_planned_days",
        "total_planned_depth",
        "depth_unit_id",
        "reopen_remarks",
        "reopened_at",
        "reopened_by",
        "deleted_at",
        "deleted_by",
        "is_active",
    ),
    "afe_lines": (
        "afe_id",
        "line_number",
        "catalog_item_id",
        "secondary_category_id",
        "cost_code_id",
        "unit_id",
        "hole_section_id",
        "rate_basis",
        "daily_consumption",
        "computed_quantity",
        "quantity_override_reason",
    ),
    "afe_sections": ("afe_id", "sequence", "hole_section_id", "phase"),
    "afe_audit_logs": ("afe_id", "action", "new_status", "created_at", "updated_at"),
    "audit_logs": ("actor_id", "action", "entity_type", "created_at"),
    "drilling_phases": ("code", "name", "sequence"),
    "daily_cost_entries": ("well_id", "afe_id", "entry_date", "cumulative_cost", "sub_activity_id"),
    "daily_cost_service_lines": ("daily_cost_entry_id", "afe_line_id", "amount"),
    "daily_cost_consumable_lines": ("daily_cost_entry_id", "afe_line_id", "amount"),
    "primary_categories": ("code", "name", "is_active"),
    "secondary_categories": ("code", "name", "primary_category_id", "is_active"),
    "tertiary_categories": ("code", "name", "secondary_category_id", "is_active"),
    "activities": ("code", "name", "sequence", "is_active"),
    "well_activities": ("well_id", "activity_id", "name", "is_active"),
    "afe_cost_estimate_lines": ("afe_id", "afe_line_id", "unit_rate", "is_active"),
}

REMEDIATION = (
    "The database schema is behind the application code. Apply the pending "
    "migrations with `cd backend && python -m alembic upgrade head` (the local "
    "dev servers do this automatically on startup) and then reload the page."
)


def _alembic_config() -> Any:
    """Build an Alembic config bound to the backend's own ini and scripts."""
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPTS))
    return config


def expected_head_revision() -> str | None:
    """The migration revision this code was shipped with, if discoverable."""
    try:
        from alembic.script import ScriptDirectory

        return ScriptDirectory.from_config(_alembic_config()).get_current_head()
    except Exception as exc:  # pragma: no cover - defensive; config is local
        logger.warning("Could not resolve the expected schema revision", extra={"error": str(exc)})
        return None


def current_revision(session: Session) -> str | None:
    """The revision recorded in the live database, if the table exists."""
    inspector = inspect(session.get_bind())
    if "alembic_version" not in inspector.get_table_names():
        return None
    try:
        return session.scalar(text("SELECT version_num FROM alembic_version"))
    except SQLAlchemyError:
        return None


def _missing_schema_parts(session: Session) -> tuple[list[str], list[str]]:
    """Tables/columns the application needs but the database does not have."""
    inspector = inspect(session.get_bind())
    existing_tables = set(inspector.get_table_names())
    missing_tables: list[str] = []
    missing_columns: list[str] = []
    for table, columns in CRITICAL_SCHEMA.items():
        if table not in existing_tables:
            missing_tables.append(table)
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table)}
        for column in columns:
            if column not in existing_columns:
                missing_columns.append(f"{table}.{column}")
    return missing_tables, missing_columns


def detect_schema_drift(session: Session) -> dict[str, Any] | None:
    """Return an explanation when the database schema is behind the code.

    ``None`` means the schema looks current. The returned mapping always
    carries ``message`` plus whatever evidence was found.
    """
    expected = expected_head_revision()
    try:
        missing_tables, missing_columns = _missing_schema_parts(session)
    except SQLAlchemyError as exc:
        return {
            "message": "The database schema could not be verified: " + str(exc).split("\n")[0],
            "expected_revision": expected,
            "current_revision": current_revision(session),
        }

    problems: list[str] = []
    if missing_tables:
        problems.append("missing tables: " + ", ".join(missing_tables))
    if missing_columns:
        problems.append("missing columns: " + ", ".join(missing_columns))
    if not problems:
        return None

    recorded = current_revision(session)
    message = (
        "The database schema is behind the application code. Apply the pending "
        "migrations with `cd backend && python -m alembic upgrade head` (the local "
        "dev servers do this automatically on startup) and then reload the page."
    )
    return {
        "message": message,
        "expected_revision": expected,
        "current_revision": recorded,
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "details": "; ".join(problems),
    }


def auto_upgrade_head(
    settings: Settings,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Apply pending migrations for local environments; never raise.

    Development and Termux databases drift out from under the code when a
    new checkout starts against an older schema, and the resulting failures
    look like random 500s. Retries absorb two processes (uvicorn --reload
    supervisor and worker) migrating at the same time on boot.
    """
    if not settings.AUTO_MIGRATE or settings.ENVIRONMENT not in {"development", "termux"}:
        return

    from alembic import command

    config = _alembic_config()
    config.set_main_option(
        "sqlalchemy.url",
        # Percent signs (e.g. percent-encoded password characters) must be
        # doubled for configparser or set_main_option raises ValueError.
        escape_for_alembic(settings.MIGRATION_DATABASE_URL or settings.DATABASE_URL),
    )

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            command.upgrade(config, "head")
            logger.info("Database migrations are up to date (alembic upgrade head)")
            return
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                sleep(0.5 * attempt)
    logger.error(
        "Automatic database migration failed; the database may be behind the "
        "application schema. Run `python -m alembic upgrade head` manually in "
        "the backend directory. Error: %s",
        last_error,
    )
