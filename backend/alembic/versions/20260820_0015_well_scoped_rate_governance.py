"""well-scoped rate governance

Rates are revised centrally while up to twenty rigs drill at once, so:

* master data keeps a rate for tangibles only — the master service rate cards
  are retired because a service is priced per well,
* every master rate change is appended to ``rate_revisions`` and supersedes
  rather than overwrites the row it replaces,
* each well gets its own rate book (``well_service_rates``,
  ``well_tangible_rates``) holding a copy of the agreed rate, frozen when the
  AFE baseline is issued, with ``well_rate_revisions`` as its change log,
* charges incurred outside an approved AFE are recorded in
  ``well_unplanned_items`` instead of by editing the AFE.

Revision ID: 20260820_0015
Revises: 20260820_0014
Create Date: 2026-08-20 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0015"
down_revision: str | None = "20260820_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WELL_STATUS_CHECK = "status IN ('planning','active','suspended','completed','abandoned')"
RATE_STATUS_CHECK = "status IN ('draft','locked')"
RATE_ORIGIN_CHECK = "origin IN ('well_planning','unplanned')"
UNPLANNED_STATUS_CHECK = "status IN ('draft','submitted','approved','rejected','cancelled')"
UNPLANNED_REASON_CHECK = (
    "reason_code IN ('emergency','operational_necessity','scope_change',"
    "'afe_omission','rate_revision','other')"
)
SERVICE_RATE_SUM_CHECK = (
    "operating_rate >= 0 AND standby_rate >= 0 "
    "AND mobilisation_rate >= 0 AND demobilisation_rate >= 0 "
    "AND personnel_operating_rate >= 0 AND personnel_standby_rate >= 0 "
    "AND other_rate >= 0"
)


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
    ]


def _money(name: str) -> sa.Column:
    return sa.Column(name, sa.Numeric(18, 4), server_default="0", nullable=False)


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _sqlite_view_safe_legacy_mode() -> bool:
    """Enable legacy rename behaviour for the next table rebuild, if any.

    The reporting views (created in 0010) reference ``wells``, and SQLite
    rejects ``ALTER TABLE ... RENAME`` while a view mentions the renamed
    table, so the batch rebuild of ``wells`` fails during its final rename.
    ``PRAGMA legacy_alter_table=ON`` skips the view/FK rewriting and the
    validation, which is exactly what the rebuild wants — the replacement
    table takes the same name, so references stay valid. The previous mode
    is returned so callers can restore it.
    """
    if not _is_sqlite():
        return False
    previous = bool(op.get_bind().exec_driver_sql("PRAGMA legacy_alter_table").scalar())
    op.get_bind().exec_driver_sql("PRAGMA legacy_alter_table=ON")
    return previous


def _sqlite_restore_legacy_mode(previous: bool) -> None:
    if _is_sqlite():
        op.get_bind().exec_driver_sql("PRAGMA legacy_alter_table=" + ("ON" if previous else "OFF"))


def upgrade() -> None:
    # --- master service rate cards are retired --------------------------------
    op.drop_table("service_rate_cards")

    # --- master tangible rates gain revision lineage --------------------------
    with op.batch_alter_table("item_prices") as batch:
        batch.alter_column("vendor_id", existing_type=sa.Uuid(), nullable=True)
        batch.add_column(
            sa.Column("revision_number", sa.Integer(), server_default="1", nullable=False)
        )
        batch.add_column(sa.Column("supersedes_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("change_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            op.f("fk_item_prices_supersedes_id_item_prices"),
            "item_prices",
            ["supersedes_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_check_constraint("positive_item_price_revision", "revision_number >= 1")
    op.create_index(op.f("ix_item_prices_supersedes_id"), "item_prices", ["supersedes_id"])

    # --- master rate change log ------------------------------------------------
    op.create_table(
        "rate_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(20), server_default="item_price", nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("item_price_id", sa.Uuid(), nullable=True),
        sa.Column("previous_price_id", sa.Uuid(), nullable=True),
        sa.Column("vendor_id", sa.Uuid(), nullable=True),
        sa.Column("currency_id", sa.Uuid(), nullable=True),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("revision_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("previous_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("new_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "scope IN ('item_price')", name=op.f("ck_rate_revisions_valid_rate_revision_scope")
        ),
        sa.CheckConstraint(
            "change_type IN ('created','revised','withdrawn')",
            name=op.f("ck_rate_revisions_valid_rate_revision_change_type"),
        ),
        sa.CheckConstraint(
            "revision_number >= 1",
            name=op.f("ck_rate_revisions_positive_rate_revision_number"),
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["catalog_items.id"],
            name=op.f("fk_rate_revisions_item_id_catalog_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_price_id"],
            ["item_prices.id"],
            name=op.f("fk_rate_revisions_item_price_id_item_prices"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["previous_price_id"],
            ["item_prices.id"],
            name=op.f("fk_rate_revisions_previous_price_id_item_prices"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_rate_revisions_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_rate_revisions_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name=op.f("fk_rate_revisions_unit_id_units"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_revisions")),
    )
    for column in ("scope", "item_id", "item_price_id", "previous_price_id", "change_type"):
        op.create_index(op.f(f"ix_rate_revisions_{column}"), "rate_revisions", [column])
    op.create_index(op.f("ix_rate_revisions_effective_from"), "rate_revisions", ["effective_from"])

    # Seed the log so existing master rates start with a traceable origin.
    op.execute(
        sa.text(
            "INSERT INTO rate_revisions "
            "(id, scope, item_id, item_price_id, vendor_id, currency_id, unit_id, "
            " change_type, revision_number, new_amount, effective_from, reason, "
            " created_at, updated_at) "
            "SELECT "
            + _uuid_expression()
            + ", 'item_price', item_id, id, vendor_id, currency_id, unit_id, "
            "'created', 1, unit_price, effective_from, "
            "'Backfilled when rate revision tracking was introduced', "
            "created_at, created_at FROM item_prices"
        )
    )

    # --- wells gain the operational context the rate lock depends on -----------
    previous_legacy = _sqlite_view_safe_legacy_mode()
    with op.batch_alter_table("wells") as batch:
        batch.add_column(sa.Column("rig_name", sa.String(150), nullable=True))
        batch.add_column(
            sa.Column("status", sa.String(20), server_default="planning", nullable=False)
        )
        batch.add_column(sa.Column("spud_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("completion_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("rates_locked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("rate_lock_reference", sa.String(150), nullable=True))
        batch.create_check_constraint("valid_well_status", WELL_STATUS_CHECK)
    _sqlite_restore_legacy_mode(previous_legacy)
    op.create_index(op.f("ix_wells_rig_name"), "wells", ["rig_name"])
    op.create_index(op.f("ix_wells_status"), "wells", ["status"])

    # --- well rate book: services ---------------------------------------------
    op.create_table(
        "well_service_rates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("well_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=True),
        sa.Column("currency_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("hole_section_id", sa.Uuid(), nullable=True),
        sa.Column("rate_basis", sa.String(20), server_default="daily", nullable=False),
        _money("operating_rate"),
        _money("standby_rate"),
        _money("mobilisation_rate"),
        _money("demobilisation_rate"),
        _money("personnel_operating_rate"),
        _money("personnel_standby_rate"),
        _money("other_rate"),
        sa.Column("origin", sa.String(20), server_default="well_planning", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("contract_reference", sa.String(150), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            RATE_STATUS_CHECK, name=op.f("ck_well_service_rates_valid_well_service_rate_status")
        ),
        sa.CheckConstraint(
            RATE_ORIGIN_CHECK, name=op.f("ck_well_service_rates_valid_well_service_rate_origin")
        ),
        sa.CheckConstraint(
            "rate_basis IN ('daily','per_service','per_section','fixed')",
            name=op.f("ck_well_service_rates_valid_well_service_rate_basis"),
        ),
        sa.CheckConstraint(
            SERVICE_RATE_SUM_CHECK,
            name=op.f("ck_well_service_rates_non_negative_well_service_rates"),
        ),
        sa.ForeignKeyConstraint(
            ["well_id"],
            ["wells.id"],
            name=op.f("fk_well_service_rates_well_id_wells"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["catalog_items.id"],
            name=op.f("fk_well_service_rates_service_id_catalog_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_well_service_rates_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_well_service_rates_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name=op.f("fk_well_service_rates_unit_id_units"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["hole_section_id"],
            ["hole_sections.id"],
            name=op.f("fk_well_service_rates_hole_section_id_hole_sections"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_well_service_rates")),
        sa.UniqueConstraint(
            "well_id",
            "service_id",
            "hole_section_id",
            "rate_basis",
            name=op.f("uq_well_service_rates_scope"),
        ),
    )
    for column in (
        "well_id",
        "service_id",
        "vendor_id",
        "currency_id",
        "unit_id",
        "hole_section_id",
        "rate_basis",
        "origin",
        "status",
        "is_active",
    ):
        op.create_index(op.f(f"ix_well_service_rates_{column}"), "well_service_rates", [column])
    op.create_index(
        "ix_well_service_rates_well_status", "well_service_rates", ["well_id", "status"]
    )

    # --- well rate book: tangibles --------------------------------------------
    op.create_table(
        "well_tangible_rates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("well_id", sa.Uuid(), nullable=False),
        sa.Column("tangible_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=True),
        sa.Column("currency_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        _money("unit_rate"),
        sa.Column("master_price_id", sa.Uuid(), nullable=True),
        sa.Column("master_unit_rate", sa.Numeric(18, 4), nullable=True),
        sa.Column("master_effective_from", sa.Date(), nullable=True),
        sa.Column("is_overridden", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("origin", sa.String(20), server_default="well_planning", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("contract_reference", sa.String(150), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            RATE_STATUS_CHECK, name=op.f("ck_well_tangible_rates_valid_well_tangible_rate_status")
        ),
        sa.CheckConstraint(
            RATE_ORIGIN_CHECK, name=op.f("ck_well_tangible_rates_valid_well_tangible_rate_origin")
        ),
        sa.CheckConstraint(
            "unit_rate >= 0", name=op.f("ck_well_tangible_rates_non_negative_well_unit_rate")
        ),
        sa.ForeignKeyConstraint(
            ["well_id"],
            ["wells.id"],
            name=op.f("fk_well_tangible_rates_well_id_wells"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tangible_id"],
            ["catalog_items.id"],
            name=op.f("fk_well_tangible_rates_tangible_id_catalog_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_well_tangible_rates_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_well_tangible_rates_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name=op.f("fk_well_tangible_rates_unit_id_units"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["master_price_id"],
            ["item_prices.id"],
            name=op.f("fk_well_tangible_rates_master_price_id_item_prices"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_well_tangible_rates")),
        sa.UniqueConstraint("well_id", "tangible_id", name=op.f("uq_well_tangible_rates_scope")),
    )
    for column in (
        "well_id",
        "tangible_id",
        "vendor_id",
        "currency_id",
        "unit_id",
        "master_price_id",
        "is_overridden",
        "origin",
        "status",
        "is_active",
    ):
        op.create_index(op.f(f"ix_well_tangible_rates_{column}"), "well_tangible_rates", [column])
    op.create_index(
        "ix_well_tangible_rates_well_status", "well_tangible_rates", ["well_id", "status"]
    )

    # --- well rate change log ---------------------------------------------------
    op.create_table(
        "well_rate_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("well_id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("well_service_rate_id", sa.Uuid(), nullable=True),
        sa.Column("well_tangible_rate_id", sa.Uuid(), nullable=True),
        sa.Column("item_code", sa.String(100), nullable=False),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("change_type", sa.String(30), nullable=False),
        sa.Column("revision_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("previous_rates", sa.JSON(), nullable=True),
        sa.Column("new_rates", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint(
            "scope IN ('service','tangible')",
            name=op.f("ck_well_rate_revisions_valid_well_revision_scope"),
        ),
        sa.CheckConstraint(
            "change_type IN ('added','rate_revised','details_updated','locked',"
            "'deactivated','unplanned_added')",
            name=op.f("ck_well_rate_revisions_valid_well_revision_change_type"),
        ),
        sa.ForeignKeyConstraint(
            ["well_id"],
            ["wells.id"],
            name=op.f("fk_well_rate_revisions_well_id_wells"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["well_service_rate_id"],
            ["well_service_rates.id"],
            name=op.f("fk_well_rate_revisions_well_service_rate_id_well_service_rates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["well_tangible_rate_id"],
            ["well_tangible_rates.id"],
            name=op.f("fk_well_rate_revisions_well_tangible_rate_id_well_tangible_rates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_well_rate_revisions")),
    )
    for column in (
        "well_id",
        "scope",
        "well_service_rate_id",
        "well_tangible_rate_id",
        "item_code",
        "change_type",
    ):
        op.create_index(op.f(f"ix_well_rate_revisions_{column}"), "well_rate_revisions", [column])
    op.create_index(
        "ix_well_rate_revisions_well_created", "well_rate_revisions", ["well_id", "created_at"]
    )

    # --- out-of-AFE register ----------------------------------------------------
    op.create_table(
        "well_unplanned_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("well_id", sa.Uuid(), nullable=False),
        sa.Column("reference", sa.String(50), nullable=False),
        sa.Column("afe_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("item_kind", sa.String(20), nullable=False),
        sa.Column("catalog_item_id", sa.Uuid(), nullable=True),
        sa.Column("item_description", sa.String(255), nullable=False),
        sa.Column("well_service_rate_id", sa.Uuid(), nullable=True),
        sa.Column("well_tangible_rate_id", sa.Uuid(), nullable=True),
        sa.Column("cost_code_id", sa.Uuid(), nullable=True),
        sa.Column("vendor_id", sa.Uuid(), nullable=True),
        sa.Column("currency_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        _money("quantity"),
        _money("unit_rate"),
        _money("amount"),
        sa.Column("reason_code", sa.String(30), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("incurred_on", sa.Date(), nullable=False),
        sa.Column("source_document_reference", sa.String(150), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            UNPLANNED_STATUS_CHECK, name=op.f("ck_well_unplanned_items_valid_unplanned_status")
        ),
        sa.CheckConstraint(
            UNPLANNED_REASON_CHECK,
            name=op.f("ck_well_unplanned_items_valid_unplanned_reason_code"),
        ),
        sa.CheckConstraint(
            "item_kind IN ('service','tangible','other')",
            name=op.f("ck_well_unplanned_items_valid_unplanned_item_kind"),
        ),
        sa.CheckConstraint(
            "quantity >= 0 AND unit_rate >= 0",
            name=op.f("ck_well_unplanned_items_non_negative_unplanned_amounts"),
        ),
        sa.ForeignKeyConstraint(
            ["well_id"],
            ["wells.id"],
            name=op.f("fk_well_unplanned_items_well_id_wells"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["afe_snapshot_id"],
            ["afe_snapshots.id"],
            name=op.f("fk_well_unplanned_items_afe_snapshot_id_afe_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_item_id"],
            ["catalog_items.id"],
            name=op.f("fk_well_unplanned_items_catalog_item_id_catalog_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["well_service_rate_id"],
            ["well_service_rates.id"],
            name=op.f("fk_well_unplanned_items_well_service_rate_id_well_service_rates"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["well_tangible_rate_id"],
            ["well_tangible_rates.id"],
            name=op.f("fk_well_unplanned_items_well_tangible_rate_id_well_tangible_rates"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cost_code_id"],
            ["cost_codes.id"],
            name=op.f("fk_well_unplanned_items_cost_code_id_cost_codes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_well_unplanned_items_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_well_unplanned_items_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name=op.f("fk_well_unplanned_items_unit_id_units"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_well_unplanned_items")),
        sa.UniqueConstraint("well_id", "reference", name=op.f("uq_well_unplanned_items_reference")),
    )
    for column in (
        "well_id",
        "reference",
        "afe_snapshot_id",
        "item_kind",
        "catalog_item_id",
        "well_service_rate_id",
        "well_tangible_rate_id",
        "cost_code_id",
        "vendor_id",
        "currency_id",
        "unit_id",
        "reason_code",
        "incurred_on",
        "status",
        "is_active",
    ):
        op.create_index(op.f(f"ix_well_unplanned_items_{column}"), "well_unplanned_items", [column])
    op.create_index(
        "ix_well_unplanned_items_well_status", "well_unplanned_items", ["well_id", "status"]
    )


def _uuid_expression() -> str:
    """Return a portable random-UUID expression for the backfill INSERT."""

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        return "gen_random_uuid()"
    if dialect == "sqlite":
        return (
            "lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || "
            "substr(hex(randomblob(2)),2) || '-' || "
            "substr('89ab',abs(random()) % 4 + 1, 1) || "
            "substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6)))"
        )
    return "uuid()"


def downgrade() -> None:
    op.drop_table("well_unplanned_items")
    op.drop_table("well_rate_revisions")
    op.drop_table("well_tangible_rates")
    op.drop_table("well_service_rates")

    op.drop_index(op.f("ix_wells_status"), table_name="wells")
    op.drop_index(op.f("ix_wells_rig_name"), table_name="wells")
    previous_legacy = _sqlite_view_safe_legacy_mode()
    with op.batch_alter_table("wells") as batch:
        batch.drop_constraint("valid_well_status", type_="check")
        batch.drop_column("rate_lock_reference")
        batch.drop_column("rates_locked_at")
        batch.drop_column("completion_date")
        batch.drop_column("spud_date")
        batch.drop_column("status")
        batch.drop_column("rig_name")
    _sqlite_restore_legacy_mode(previous_legacy)

    op.drop_table("rate_revisions")

    op.drop_index(op.f("ix_item_prices_supersedes_id"), table_name="item_prices")
    with op.batch_alter_table("item_prices") as batch:
        batch.drop_constraint("positive_item_price_revision", type_="check")
        batch.drop_constraint(op.f("fk_item_prices_supersedes_id_item_prices"), type_="foreignkey")
        batch.drop_column("superseded_at")
        batch.drop_column("change_reason")
        batch.drop_column("supersedes_id")
        batch.drop_column("revision_number")
        batch.alter_column("vendor_id", existing_type=sa.Uuid(), nullable=False)

    # Recreated empty, in exactly the shape revision 0014 left behind, so the
    # earlier downgrades still find the constraints and columns they drop.
    op.create_table(
        "service_rate_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("currency_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("hole_section_id", sa.Uuid(), nullable=True),
        sa.Column("rate_basis", sa.String(20), server_default="daily", nullable=False),
        _money("operating_rate"),
        _money("standby_rate"),
        _money("mobilisation_rate"),
        _money("demobilisation_rate"),
        _money("personnel_operating_rate"),
        _money("personnel_standby_rate"),
        _money("other_rate"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_audit_columns(),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_service_rate_cards_valid_service_rate_range"),
        ),
        sa.CheckConstraint(
            SERVICE_RATE_SUM_CHECK,
            name=op.f("ck_service_rate_cards_non_negative_service_rates"),
        ),
        sa.CheckConstraint(
            "rate_basis IN ('daily','per_service','per_section','fixed')",
            name=op.f("ck_service_rate_cards_valid_service_rate_basis"),
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["catalog_items.id"],
            name=op.f("fk_service_rate_cards_service_id_catalog_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_service_rate_cards_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_service_rate_cards_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name=op.f("fk_service_rate_cards_unit_id_units"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["hole_section_id"],
            ["hole_sections.id"],
            name=op.f("fk_service_rate_cards_hole_section_id_hole_sections"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_rate_cards")),
    )
    for column in (
        "service_id",
        "vendor_id",
        "currency_id",
        "unit_id",
        "hole_section_id",
        "rate_basis",
        "effective_from",
        "effective_to",
        "is_active",
    ):
        op.create_index(op.f(f"ix_service_rate_cards_{column}"), "service_rate_cards", [column])
