"""merge well requirements into AFE

Well requirements and the AFE were two names for the same document, so the
requirement tables become the AFE tables:

* ``well_requirements`` -> ``afes`` and ``requirement_items`` -> ``afe_lines``,
  with every constraint, index, and foreign key renamed to match,
* ``cost_estimates.requirement_id`` -> ``afe_id`` and
  ``estimate_items.requirement_item_id`` -> ``afe_line_id``,
* ``afe_snapshots.requirement_code`` -> ``afe_code``,
* the reporting contract views are rebuilt on the renamed tables.

The AFE line also gains the fields the planners asked for:

* ``hole_section_id`` replaces the free-text ``section_name`` — sections now
  come from the hole-section configuration, and existing text is matched to a
  configured section by code or name where it can be,
* ``rate_basis`` records how the line is charged (daily, per section, per
  service, fixed, per unit, or daily consumption), defaulted from the
  catalogue item and overridable per line, and
* ``daily_consumption`` / ``computed_quantity`` / ``quantity_override_reason``
  carry the chemical and additive daily-usage calculation and any reasoned
  manual override of the computed total.

Mud chemicals and cement additives also gain their own ``rate_basis`` so the
catalogue can say which of them are charged on daily usage.

Revision ID: 20260821_0017
Revises: 20260820_0016
Create Date: 2026-08-21 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "20260821_0017"
down_revision: str | None = "20260820_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LINE_RATE_BASIS_CHECK = (
    "rate_basis IN ('daily','per_service','per_section','fixed','per_unit','daily_consumption')"
)
CONSUMABLE_RATE_BASIS_CHECK = "rate_basis IN ('per_unit','daily_consumption')"

TABLE_RENAMES = [("well_requirements", "afes"), ("requirement_items", "afe_lines")]

INDEX_RENAMES = [
    ("ix_well_requirements_code", "ix_afes_code", "afes"),
    ("ix_well_requirements_is_active", "ix_afes_is_active", "afes"),
    ("ix_well_requirements_status", "ix_afes_status", "afes"),
    ("ix_well_requirements_supersedes_id", "ix_afes_supersedes_id", "afes"),
    ("ix_well_requirements_title", "ix_afes_title", "afes"),
    ("ix_well_requirements_well_id", "ix_afes_well_id", "afes"),
    ("ix_requirement_items_catalog_item_id", "ix_afe_lines_catalog_item_id", "afe_lines"),
    ("ix_requirement_items_cost_code_id", "ix_afe_lines_cost_code_id", "afe_lines"),
    ("ix_requirement_items_depth_unit_id", "ix_afe_lines_depth_unit_id", "afe_lines"),
    ("ix_requirement_items_is_active", "ix_afe_lines_is_active", "afe_lines"),
    ("ix_requirement_items_requirement_id", "ix_afe_lines_afe_id", "afe_lines"),
    ("ix_requirement_items_unit_id", "ix_afe_lines_unit_id", "afe_lines"),
]

CONSTRAINT_RENAMES = [
    ("afes", "pk_well_requirements", "pk_afes"),
    ("afes", "uq_requirements_well_code_revision", "uq_afes_well_code_revision"),
    ("afes", "ck_well_requirements_valid_status", "ck_afes_valid_status"),
    ("afes", "ck_well_requirements_positive_revision", "ck_afes_positive_revision"),
    ("afes", "fk_well_requirements_well_id_wells", "fk_afes_well_id_wells"),
    ("afes", "fk_well_requirements_supersedes_id_well_requirements", "fk_afes_supersedes_id_afes"),
    ("afe_lines", "pk_requirement_items", "pk_afe_lines"),
    ("afe_lines", "uq_requirement_items_requirement_line", "uq_afe_lines_afe_line"),
    ("afe_lines", "ck_requirement_items_positive_line_number", "ck_afe_lines_positive_line_number"),
    ("afe_lines", "ck_requirement_items_valid_depth_range", "ck_afe_lines_valid_depth_range"),
    (
        "afe_lines",
        "ck_requirement_items_non_negative_duration",
        "ck_afe_lines_non_negative_duration",
    ),
    (
        "afe_lines",
        "ck_requirement_items_non_negative_quantity",
        "ck_afe_lines_non_negative_quantity",
    ),
    (
        "afe_lines",
        "fk_requirement_items_catalog_item_id_catalog_items",
        "fk_afe_lines_catalog_item_id_catalog_items",
    ),
    (
        "afe_lines",
        "fk_requirement_items_cost_code_id_cost_codes",
        "fk_afe_lines_cost_code_id_cost_codes",
    ),
    ("afe_lines", "fk_requirement_items_depth_unit_id_units", "fk_afe_lines_depth_unit_id_units"),
    (
        "afe_lines",
        "fk_requirement_items_requirement_id_well_requirements",
        "fk_afe_lines_afe_id_afes",
    ),
    ("afe_lines", "fk_requirement_items_unit_id_units", "fk_afe_lines_unit_id_units"),
    (
        "cost_estimates",
        "fk_cost_estimates_requirement_id_well_requirements",
        "fk_cost_estimates_afe_id_afes",
    ),
    (
        "estimate_items",
        "fk_estimate_items_requirement_item_id_requirement_items",
        "fk_estimate_items_afe_line_id_afe_lines",
    ),
]

REPORTING_VIEWS = [
    "v1_contract_metadata",
    "v1_reporting_policy",
    "v1_dim_afe",
    "v1_dim_currency",
    "v1_dim_vendor",
    "v1_dim_cost_code",
    "v1_dim_well",
    "v1_dim_project",
    "v1_cost_transaction_fact",
]


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _sqlite_allow_reference_rewrites() -> None:
    """Re-enable SQLite's FOREIGN KEY clause rewriting for RENAME.

    Earlier migrations' batch operations leave ``PRAGMA legacy_alter_table``
    ON for the shared migration connection. With it ON, ``ALTER TABLE ...
    RENAME`` does *not* update the FOREIGN KEY clauses of the tables that
    reference the renamed one, so the renames below would leave ``afe_lines``
    still pointing at ``well_requirements`` and the following batch
    reflection would fail with ``NoSuchTableError``. Here the rewrite is
    exactly what is wanted — references should follow the new table names.
    """

    if _is_sqlite():
        op.get_bind().exec_driver_sql("PRAGMA legacy_alter_table=OFF")


# ── reporting contract views ─────────────────────────────────────────────────


def _drop_reporting_views() -> None:
    if _is_sqlite():
        for view in REPORTING_VIEWS:
            op.execute(text(f"DROP VIEW IF EXISTS rpt_{view}"))
        return
    for view in REPORTING_VIEWS:
        op.execute(f"DROP VIEW IF EXISTS reporting.{view}")


def _fact_sql(afe_table: str, afe_id_column: str, afe_code_column: str) -> str:
    """The transaction fact view, parameterised so it can be rebuilt either way."""

    return f"""
        SELECT
            txn.id AS transaction_id,
            txn.posting_reference,
            txn.cost_state,
            txn.transaction_date AS transaction_date,
            txn.currency_code,
            txn.amount AS source_amount,
            txn.quantity,
            txn.unit_code,
            txn.cost_code,
            category.code AS cost_category_code,
            NULL AS item_nature,
            txn.vendor_code,
            txn.source_document_type,
            txn.source_document_reference,
            txn.external_transaction_id AS external_transaction_id,
            txn.correction_kind,
            txn.reverses_transaction_id AS reverses_transaction_id,
            snapshot.id AS afe_snapshot_id,
            snapshot.afe_number,
            snapshot.issue_date AS afe_issue_date,
            version.id AS estimate_version_id,
            version.version_number AS estimate_version_number,
            estimate.id AS estimate_id,
            estimate.code AS estimate_code,
            afe.id AS {afe_id_column},
            afe.code AS {afe_code_column},
            well.id AS well_id,
            well.code AS well_code,
            project.id AS project_id,
            project.code AS project_code,
            txn.created_at AS posted_at,
            txn.created_by AS posted_by
        FROM cost_transactions AS txn
        JOIN afe_snapshots AS snapshot ON snapshot.id = txn.afe_snapshot_id
        JOIN estimate_versions AS version ON version.id = snapshot.estimate_version_id
        JOIN cost_estimates AS estimate ON estimate.id = version.estimate_id
        JOIN {afe_table} AS afe ON afe.id = estimate.{afe_id_column}
        JOIN wells AS well ON well.id = afe.well_id
        JOIN projects AS project ON project.id = well.project_id
        LEFT JOIN cost_codes AS cost_code ON cost_code.code = txn.cost_code
        LEFT JOIN cost_categories AS category ON category.id = cost_code.cost_category_id
    """


def _dim_afe_sql(snapshot_code_column: str) -> str:
    return f"""
        SELECT snapshot.id AS afe_snapshot_id, snapshot.afe_number, snapshot.issue_date,
               snapshot.currency_code, snapshot.estimate_version_id, version.version_number,
               estimate.id AS estimate_id, estimate.code AS estimate_code,
               snapshot.project_code, snapshot.well_code, snapshot.{snapshot_code_column},
               snapshot.engine_version, snapshot.rule_set_version,
               snapshot.created_at, snapshot.created_by
        FROM afe_snapshots AS snapshot
        JOIN estimate_versions AS version ON version.id = snapshot.estimate_version_id
        JOIN cost_estimates AS estimate ON estimate.id = version.estimate_id
    """


SIMPLE_VIEWS: dict[str, str] = {
    "v1_dim_project": """
        SELECT id AS project_id, code AS project_code, name AS project_name,
               description, is_active, created_at, updated_at
        FROM projects
    """,
    "v1_dim_well": """
        SELECT well.id AS well_id, well.code AS well_code, well.name AS well_name,
               well.project_id, project.code AS project_code, well.is_active,
               well.created_at, well.updated_at
        FROM wells AS well
        JOIN projects AS project ON project.id = well.project_id
    """,
    "v1_dim_cost_code": """
        SELECT cost_code.id AS cost_code_id, cost_code.code AS cost_code,
               cost_code.name AS cost_code_name, category.id AS cost_category_id,
               category.code AS cost_category_code, category.name AS cost_category_name,
               cost_code.is_active, cost_code.created_at, cost_code.updated_at
        FROM cost_codes AS cost_code
        JOIN cost_categories AS category ON category.id = cost_code.cost_category_id
    """,
    "v1_dim_vendor": """
        SELECT id AS vendor_id, code AS vendor_code, name AS vendor_name,
               description, is_active, created_at, updated_at
        FROM vendors
    """,
    "v1_dim_currency": """
        SELECT id AS currency_id, code AS currency_code, name AS currency_name,
               symbol, is_active, created_at, updated_at
        FROM currencies
    """,
    "v1_reporting_policy": """
        SELECT 'reporting_currency' AS metric_key, 'policy_pending' AS status,
               'Reporting currency and FX basis' AS description
        UNION ALL SELECT 'afe_family', 'policy_pending',
               'AFE baseline/revision/supplement inclusion'
        UNION ALL SELECT 'cost_state_overlap', 'policy_pending',
               'State overlap and reconciliation'
        UNION ALL SELECT 'variance_to_afe', 'policy_pending',
               'Variance formula and sign convention'
        UNION ALL SELECT 'forecast_at_completion', 'policy_pending',
               'Forecast and EAC methodology'
        UNION ALL SELECT 'rounding_cutoff', 'policy_pending',
               'Rounding, cut-off, reversals, and zero budgets'
    """,
    "v1_contract_metadata": """
        SELECT '1.0' AS contract_version,
               'framework' AS contract_status,
               '2026-08-13' AS published_date,
               'policy_pending' AS financial_metrics_status,
               'not_applied' AS direct_grants_status
    """,
}


def _create_reporting_views(
    *, afe_table: str, afe_id_column: str, afe_code_column: str, snapshot_code_column: str
) -> None:
    definitions = {
        "v1_cost_transaction_fact": _fact_sql(afe_table, afe_id_column, afe_code_column),
        **SIMPLE_VIEWS,
        "v1_dim_afe": _dim_afe_sql(snapshot_code_column),
    }
    for view, body in definitions.items():
        if _is_sqlite():
            op.execute(text(f"CREATE VIEW IF NOT EXISTS rpt_{view} AS {body}"))
        else:
            op.execute(f"CREATE VIEW reporting.{view} AS {body}")


# ── upgrade ──────────────────────────────────────────────────────────────────


def upgrade() -> None:
    _drop_reporting_views()
    _sqlite_allow_reference_rewrites()

    for old, new in TABLE_RENAMES:
        op.rename_table(old, new)
    for old, new, table in INDEX_RENAMES:
        _rename_index(old, new, table)
    for table, old, new in CONSTRAINT_RENAMES:
        _rename_constraint(table, old, new)

    with op.batch_alter_table("afe_lines") as batch:
        batch.alter_column("requirement_id", new_column_name="afe_id")
    with op.batch_alter_table("cost_estimates") as batch:
        batch.alter_column("requirement_id", new_column_name="afe_id")
    with op.batch_alter_table("estimate_items") as batch:
        batch.alter_column("requirement_item_id", new_column_name="afe_line_id")
    with op.batch_alter_table("afe_snapshots") as batch:
        batch.alter_column("requirement_code", new_column_name="afe_code")

    _rename_index("ix_cost_estimates_requirement_id", "ix_cost_estimates_afe_id", "cost_estimates")
    _rename_index(
        "ix_estimate_items_requirement_item_id", "ix_estimate_items_afe_line_id", "estimate_items"
    )

    # --- AFE line: configured section, rate basis, daily consumption ---------
    op.add_column("afe_lines", sa.Column("hole_section_id", sa.Uuid(), nullable=True))
    if not _is_sqlite():  # SQLite cannot add constraints to existing tables
        op.create_foreign_key(
            op.f("fk_afe_lines_hole_section_id_hole_sections"),
            "afe_lines",
            "hole_sections",
            ["hole_section_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index(op.f("ix_afe_lines_hole_section_id"), "afe_lines", ["hole_section_id"])

    # Existing free text becomes a configured section wherever one matches.
    op.execute(
        """
        UPDATE afe_lines
        SET hole_section_id = (
            SELECT hole_sections.id FROM hole_sections
            WHERE upper(trim(hole_sections.code)) = upper(trim(afe_lines.section_name))
               OR upper(trim(hole_sections.name)) = upper(trim(afe_lines.section_name))
            LIMIT 1
        )
        WHERE section_name IS NOT NULL
        """
    )

    op.add_column(
        "afe_lines",
        sa.Column("rate_basis", sa.String(20), server_default="daily", nullable=False),
    )
    op.add_column("afe_lines", sa.Column("daily_consumption", sa.Numeric(18, 4), nullable=True))
    op.add_column("afe_lines", sa.Column("computed_quantity", sa.Numeric(18, 4), nullable=True))
    op.add_column("afe_lines", sa.Column("quantity_override_reason", sa.Text(), nullable=True))
    op.create_index(op.f("ix_afe_lines_rate_basis"), "afe_lines", ["rate_basis"])
    if not _is_sqlite():  # SQLite cannot add constraints to existing tables
        op.create_check_constraint("valid_rate_basis", "afe_lines", LINE_RATE_BASIS_CHECK)
        op.create_check_constraint(
            "non_negative_daily_consumption",
            "afe_lines",
            "daily_consumption IS NULL OR daily_consumption >= 0",
        )
        op.create_check_constraint(
            "non_negative_computed_quantity",
            "afe_lines",
            "computed_quantity IS NULL OR computed_quantity >= 0",
        )
        op.create_check_constraint(
            "override_reason_not_blank",
            "afe_lines",
            "quantity_override_reason IS NULL OR length(trim(quantity_override_reason)) > 0",
        )

    # Lines already recorded keep the basis their catalogue item is charged on:
    # services carry theirs, equipment defaults to daily, everything else per unit.
    op.execute(
        """
        UPDATE afe_lines
        SET rate_basis = COALESCE(
            (
                SELECT services.rate_basis FROM services
                WHERE services.id = afe_lines.catalog_item_id
            ),
            (
                SELECT CASE WHEN catalog_items.item_type = 'equipment' THEN 'daily'
                            ELSE 'per_unit' END
                FROM catalog_items WHERE catalog_items.id = afe_lines.catalog_item_id
            ),
            'per_unit'
        )
        """
    )

    op.drop_index(op.f("ix_requirement_items_section_name"), table_name="afe_lines")
    op.drop_column("afe_lines", "section_name")

    # --- chemicals and additives: how they are charged -----------------------
    for table in ("mud_chemicals", "cement_additives"):
        op.add_column(
            table,
            sa.Column("rate_basis", sa.String(20), server_default="per_unit", nullable=False),
        )
        op.create_index(op.f(f"ix_{table}_rate_basis"), table, ["rate_basis"])
        if not _is_sqlite():  # SQLite cannot add constraints to existing tables
            op.create_check_constraint(
                f"valid_{table[:-1]}_rate_basis", table, CONSUMABLE_RATE_BASIS_CHECK
            )

    _create_reporting_views(
        afe_table="afes",
        afe_id_column="afe_id",
        afe_code_column="afe_code",
        snapshot_code_column="afe_code",
    )


# ── downgrade ────────────────────────────────────────────────────────────────


def downgrade() -> None:
    _drop_reporting_views()

    for table in ("cement_additives", "mud_chemicals"):
        if not _is_sqlite():  # constraints were never created on SQLite
            op.drop_constraint(f"valid_{table[:-1]}_rate_basis", table, type_="check")
        op.drop_index(op.f(f"ix_{table}_rate_basis"), table_name=table)
        op.drop_column(table, "rate_basis")

    op.add_column("afe_lines", sa.Column("section_name", sa.String(150), nullable=True))
    op.execute(
        """
        UPDATE afe_lines
        SET section_name = (
            SELECT hole_sections.name FROM hole_sections
            WHERE hole_sections.id = afe_lines.hole_section_id
        )
        WHERE hole_section_id IS NOT NULL
        """
    )
    op.create_index(
        op.f("ix_requirement_items_section_name"), "afe_lines", ["section_name"], unique=False
    )

    for constraint in (
        "override_reason_not_blank",
        "non_negative_computed_quantity",
        "non_negative_daily_consumption",
        "valid_rate_basis",
    ):
        if not _is_sqlite():  # constraints were never created on SQLite
            op.drop_constraint(constraint, "afe_lines", type_="check")
    op.drop_index(op.f("ix_afe_lines_rate_basis"), table_name="afe_lines")
    for column in (
        "quantity_override_reason",
        "computed_quantity",
        "daily_consumption",
        "rate_basis",
    ):
        op.drop_column("afe_lines", column)

    op.drop_index(op.f("ix_afe_lines_hole_section_id"), table_name="afe_lines")
    if not _is_sqlite():  # foreign key was never created on SQLite
        op.drop_constraint(
            op.f("fk_afe_lines_hole_section_id_hole_sections"),
            "afe_lines",
            type_="foreignkey",
        )
    op.drop_column("afe_lines", "hole_section_id")

    _rename_index("ix_cost_estimates_afe_id", "ix_cost_estimates_requirement_id", "cost_estimates")
    _rename_index(
        "ix_estimate_items_afe_line_id", "ix_estimate_items_requirement_item_id", "estimate_items"
    )
    with op.batch_alter_table("afe_snapshots") as batch:
        batch.alter_column("afe_code", new_column_name="requirement_code")
    with op.batch_alter_table("estimate_items") as batch:
        batch.alter_column("afe_line_id", new_column_name="requirement_item_id")
    with op.batch_alter_table("cost_estimates") as batch:
        batch.alter_column("afe_id", new_column_name="requirement_id")
    with op.batch_alter_table("afe_lines") as batch:
        batch.alter_column("afe_id", new_column_name="requirement_id")

    for table, old, new in CONSTRAINT_RENAMES:
        _rename_constraint(table, new, old)
    for old, new, table in INDEX_RENAMES:
        _rename_index(new, old, table)
    _sqlite_allow_reference_rewrites()
    for old, new in TABLE_RENAMES:
        op.rename_table(new, old)

    _create_reporting_views(
        afe_table="well_requirements",
        afe_id_column="requirement_id",
        afe_code_column="requirement_code",
        snapshot_code_column="requirement_code",
    )


def _rename_constraint(table: str, old: str, new: str) -> None:
    """Renaming a table leaves its constraint names behind on PostgreSQL.

    SQLite has no ALTER CONSTRAINT and does not enforce the names, so it is
    skipped there; ``create_all`` in the test suite already builds the new ones.
    """

    if _is_sqlite():
        return
    op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT "{old}" TO "{new}"')


def _rename_index(old: str, new: str, table: str) -> None:
    """Rename an index on either dialect; SQLite has no ALTER INDEX."""

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        inspector = sa.inspect(bind)
        for index in inspector.get_indexes(table):
            if index["name"] == old:
                op.drop_index(old, table_name=table)
                op.create_index(
                    new, table, list(index["column_names"]), unique=bool(index["unique"])
                )
                return
        return
    op.execute(f'ALTER INDEX IF EXISTS "{old}" RENAME TO "{new}"')
