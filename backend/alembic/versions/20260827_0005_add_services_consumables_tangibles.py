"""Add Services, Consumables (Mud Chemicals + Drill Bits) and Tangibles catalogues.

Revision ID: 20260827_0005
Revises: 20260827_0004
Create Date: 2026-08-27

Adds:
* catalogue_configs          - user-configurable dropdown lists
* consumable_subcategories   - Mud Chemicals / Cement Additives / Fuel / Drill Bits
* services                   - Service catalogue
* mud_chemicals (+ rates)    - consumable items with rate revision history
* drill_bits (+ rates)       - consumable items with rate revision history
* tangibles (+ rates)        - tangible items with rate revision history
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.db.migration_ops import (
    create_index_if_missing,
    create_table_if_missing,
    drop_index_if_present,
    drop_table_if_present,
)

# Databases provisioned by an older build can hold these catalogue tables with
# UUID primary keys and none of the code columns defined here. Such a table can
# neither be mapped by the ORM nor referenced by the rate tables below
# (PostgreSQL rejects the foreign key with DatatypeMismatch), so it is renamed
# aside with this suffix and replaced by the table this revision defines.
LEGACY_TABLE_SUFFIX = "pre_20260827_0005"

revision: str = "20260827_0005"
down_revision: str | None = "20260827_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Common soft-delete + timestamp + audit actor columns shared by the business
# tables, mirroring the ORM mixins.
def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
    ]


def upgrade() -> None:
    # --- Configurable dropdown lists -------------------------------------
    create_table_if_missing(
        "catalogue_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("config_type", sa.String(length=50), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("system_seeded", sa.Boolean(), server_default="false", nullable=False),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalogue_configs")),
        sa.UniqueConstraint("config_type", "value", name=op.f("uq_catalogue_configs_type_value")),
        incompatible_pk_suffix=LEGACY_TABLE_SUFFIX,
    )
    create_index_if_missing(op.f("ix_catalogue_configs_config_type"), "catalogue_configs", ["config_type"])

    # --- Consumable subcategories ----------------------------------------
    create_table_if_missing(
        "consumable_subcategories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subcategory_code", sa.String(length=20), nullable=False),
        sa.Column("subcategory_name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("entry_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consumable_subcategories")),
        incompatible_pk_suffix=LEGACY_TABLE_SUFFIX,
    )
    create_index_if_missing(
        op.f("ix_consumable_subcategories_subcategory_code"),
        "consumable_subcategories",
        ["subcategory_code"],
        unique=True,
    )

    # Seed the fixed consumable subcategory directory. Guarded per row so a
    # re-run over an existing/partially-provisioned table (idempotent replay
    # scenario) never hits a duplicate-key error.
    seed_subcategories = [
        ("MC", "Mud Chemicals", 1, True, "Drilling mud chemicals with periodic rate revisions"),
        ("CA", "Cement Additives", 2, False, "Cement additives - item entry configured in a later release"),
        ("FU", "Fuel", 3, False, "Fuel (AGO, PMS, Others) - item entry configured in a later release"),
        ("DB", "Drill Bits", 4, True, "Drill bits by make/specification with periodic rate revisions"),
    ]
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_codes: set[str] = set()
    if "consumable_subcategories" in inspector.get_table_names():
        existing_codes = {
            str(row[0])
            for row in bind.execute(sa.text("SELECT subcategory_code FROM consumable_subcategories")).fetchall()
        }
    # Insert with typed parameters so booleans bind correctly on both
    # backends: untyped sa.table() bulk_insert would send Python booleans as
    # text ('true'/'false'), which PostgreSQL rejects against Boolean columns
    # and SQLite stores as strings instead of 0/1.
    insert_sql = sa.text(
        "INSERT INTO consumable_subcategories "
        "(subcategory_code, subcategory_name, sort_order, entry_enabled, "
        " description, is_deleted, created_at, updated_at) "
        "VALUES (:code, :name, :sort_order, :entry_enabled, :description, "
        " false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    for code, name, sort_order, entry_enabled, description in seed_subcategories:
        if code in existing_codes:
            continue
        bind.execute(
            insert_sql,
            {
                "code": code,
                "name": name,
                "sort_order": sort_order,
                "entry_enabled": bool(entry_enabled),
                "description": description,
            },
        )

    # --- Services --------------------------------------------------------
    create_table_if_missing(
        "services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("service_code", sa.String(length=50), nullable=False),
        sa.Column("service_name", sa.String(length=200), nullable=False),
        sa.Column("service_type", sa.String(length=50), server_default="Service", nullable=False),
        sa.Column("provider_type", sa.String(length=30), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendor_suppliers.id"], name=op.f("fk_services_vendor_id_vendor_suppliers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        incompatible_pk_suffix=LEGACY_TABLE_SUFFIX,
    )
    create_index_if_missing(op.f("ix_services_service_code"), "services", ["service_code"], unique=True)
    create_index_if_missing(op.f("ix_services_service_name"), "services", ["service_name"])
    create_index_if_missing(op.f("ix_services_vendor_id"), "services", ["vendor_id"])

    # --- Mud Chemicals ---------------------------------------------------
    create_table_if_missing(
        "mud_chemicals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chemical_code", sa.String(length=50), nullable=False),
        sa.Column("part_number", sa.String(length=100), nullable=True),
        sa.Column("chemical_name", sa.String(length=200), nullable=False),
        sa.Column("uom", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("current_rate", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mud_chemicals")),
        incompatible_pk_suffix=LEGACY_TABLE_SUFFIX,
    )
    create_index_if_missing(op.f("ix_mud_chemicals_chemical_code"), "mud_chemicals", ["chemical_code"], unique=True)
    create_index_if_missing(op.f("ix_mud_chemicals_chemical_name"), "mud_chemicals", ["chemical_name"])

    create_table_if_missing(
        "mud_chemical_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chemical_id", sa.Integer(), nullable=False),
        sa.Column("unit_rate", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("previous_rate", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("uom", sa.String(length=50), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("revision_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["chemical_id"], ["mud_chemicals.id"], name=op.f("fk_mud_chemical_rates_chemical_id_mud_chemicals")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mud_chemical_rates")),
        incompatible_pk_suffix=LEGACY_TABLE_SUFFIX,
    )
    create_index_if_missing(op.f("ix_mud_chemical_rates_chemical_id"), "mud_chemical_rates", ["chemical_id"])
    create_index_if_missing(op.f("ix_mud_chemical_rates_effective_date"), "mud_chemical_rates", ["effective_date"])

    # --- Drill Bits ------------------------------------------------------
    create_table_if_missing(
        "drill_bits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bit_code", sa.String(length=50), nullable=False),
        sa.Column("bit_name", sa.String(length=200), nullable=False),
        sa.Column("bit_type", sa.String(length=100), nullable=False),
        sa.Column("model_no", sa.String(length=100), nullable=False),
        sa.Column("size", sa.String(length=100), nullable=False),
        sa.Column("manufacturer", sa.String(length=200), nullable=False),
        sa.Column("po_number", sa.String(length=100), nullable=True),
        sa.Column("serial_number", sa.String(length=100), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("unit_rate_po", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("cost_uplift", sa.Numeric(precision=8, scale=2), server_default="100", nullable=False),
        sa.Column("final_cost", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drill_bits")),
        incompatible_pk_suffix=LEGACY_TABLE_SUFFIX,
    )
    create_index_if_missing(op.f("ix_drill_bits_bit_code"), "drill_bits", ["bit_code"], unique=True)
    create_index_if_missing(op.f("ix_drill_bits_bit_name"), "drill_bits", ["bit_name"])

    create_table_if_missing(
        "drill_bit_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bit_id", sa.Integer(), nullable=False),
        sa.Column("unit_rate_po", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("cost_uplift", sa.Numeric(precision=8, scale=2), server_default="100", nullable=False),
        sa.Column("final_cost", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("revision_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("po_number", sa.String(length=100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["bit_id"], ["drill_bits.id"], name=op.f("fk_drill_bit_rates_bit_id_drill_bits")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drill_bit_rates")),
        incompatible_pk_suffix=LEGACY_TABLE_SUFFIX,
    )
    create_index_if_missing(op.f("ix_drill_bit_rates_bit_id"), "drill_bit_rates", ["bit_id"])
    create_index_if_missing(op.f("ix_drill_bit_rates_effective_date"), "drill_bit_rates", ["effective_date"])

    # --- Tangibles -------------------------------------------------------
    create_table_if_missing(
        "tangibles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tangible_code", sa.String(length=50), nullable=False),
        sa.Column("tangible_scope", sa.String(length=30), nullable=False),
        sa.Column("category", sa.String(length=200), nullable=False),
        sa.Column("subcategory", sa.String(length=200), nullable=False),
        sa.Column("manufacturer", sa.String(length=200), nullable=False),
        sa.Column("po_number", sa.String(length=100), nullable=True),
        sa.Column("tangible_name", sa.String(length=200), nullable=False),
        sa.Column("uom", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("unit_rate_po", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("cost_uplift", sa.Numeric(precision=8, scale=2), server_default="100", nullable=False),
        sa.Column("final_cost", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tangibles")),
        incompatible_pk_suffix=LEGACY_TABLE_SUFFIX,
    )
    create_index_if_missing(op.f("ix_tangibles_tangible_code"), "tangibles", ["tangible_code"], unique=True)
    create_index_if_missing(op.f("ix_tangibles_tangible_name"), "tangibles", ["tangible_name"])
    create_index_if_missing(op.f("ix_tangibles_tangible_scope"), "tangibles", ["tangible_scope"])

    create_table_if_missing(
        "tangible_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tangible_id", sa.Integer(), nullable=False),
        sa.Column("unit_rate_po", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("cost_uplift", sa.Numeric(precision=8, scale=2), server_default="100", nullable=False),
        sa.Column("final_cost", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("revision_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("po_number", sa.String(length=100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["tangible_id"], ["tangibles.id"], name=op.f("fk_tangible_rates_tangible_id_tangibles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tangible_rates")),
        incompatible_pk_suffix=LEGACY_TABLE_SUFFIX,
    )
    create_index_if_missing(op.f("ix_tangible_rates_tangible_id"), "tangible_rates", ["tangible_id"])
    create_index_if_missing(op.f("ix_tangible_rates_effective_date"), "tangible_rates", ["effective_date"])


def downgrade() -> None:
    drop_index_if_present(op.f("ix_tangible_rates_effective_date"), "tangible_rates")
    drop_index_if_present(op.f("ix_tangible_rates_tangible_id"), "tangible_rates")
    drop_table_if_present("tangible_rates")

    drop_index_if_present(op.f("ix_tangibles_tangible_scope"), "tangibles")
    drop_index_if_present(op.f("ix_tangibles_tangible_name"), "tangibles")
    drop_index_if_present(op.f("ix_tangibles_tangible_code"), "tangibles")
    drop_table_if_present("tangibles")

    drop_index_if_present(op.f("ix_drill_bit_rates_effective_date"), "drill_bit_rates")
    drop_index_if_present(op.f("ix_drill_bit_rates_bit_id"), "drill_bit_rates")
    drop_table_if_present("drill_bit_rates")

    drop_index_if_present(op.f("ix_drill_bits_bit_name"), "drill_bits")
    drop_index_if_present(op.f("ix_drill_bits_bit_code"), "drill_bits")
    drop_table_if_present("drill_bits")

    drop_index_if_present(op.f("ix_mud_chemical_rates_effective_date"), "mud_chemical_rates")
    drop_index_if_present(op.f("ix_mud_chemical_rates_chemical_id"), "mud_chemical_rates")
    drop_table_if_present("mud_chemical_rates")

    drop_index_if_present(op.f("ix_mud_chemicals_chemical_name"), "mud_chemicals")
    drop_index_if_present(op.f("ix_mud_chemicals_chemical_code"), "mud_chemicals")
    drop_table_if_present("mud_chemicals")

    drop_index_if_present(op.f("ix_services_vendor_id"), "services")
    drop_index_if_present(op.f("ix_services_service_name"), "services")
    drop_index_if_present(op.f("ix_services_service_code"), "services")
    drop_table_if_present("services")

    drop_index_if_present(
        op.f("ix_consumable_subcategories_subcategory_code"),
        "consumable_subcategories",
    )
    drop_table_if_present("consumable_subcategories")

    drop_index_if_present(op.f("ix_catalogue_configs_config_type"), "catalogue_configs")
    drop_table_if_present("catalogue_configs")
