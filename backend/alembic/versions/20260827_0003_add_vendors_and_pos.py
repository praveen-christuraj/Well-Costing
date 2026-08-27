"""Add vendor_suppliers and purchase_orders_service_orders tables.

Revision ID: 20260827_0003
Revises: 20260827_0002
Create Date: 2026-08-27
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

revision: str = "20260827_0003"
down_revision: str | None = "20260827_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Vendors/Suppliers
    create_table_if_missing(
        "vendor_suppliers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vendor_code", sa.String(length=50), nullable=False),
        sa.Column("vendor_name", sa.String(length=200), nullable=False),
        sa.Column("contact", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendor_suppliers")),
    )
    create_index_if_missing(op.f("ix_vendor_suppliers_vendor_code"), "vendor_suppliers", ["vendor_code"], unique=True)

    # Purchase Orders / Service Orders
    create_table_if_missing(
        "purchase_orders_service_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("po_type", sa.String(length=20), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("po_so_number", sa.String(length=100), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("value", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("is_amendment", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("amendment_number", sa.Integer(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("attachment_path", sa.String(length=500), nullable=True),
        sa.Column("attachment_original_name", sa.String(length=300), nullable=True),
        sa.Column("attachment_mime_type", sa.String(length=100), nullable=True),
        sa.Column("attachment_size", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendor_suppliers.id"], name=op.f("fk_purchase_orders_service_orders_vendor_id_vendor_suppliers")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_orders_service_orders")),
    )
    create_index_if_missing(op.f("ix_purchase_orders_service_orders_po_type"), "purchase_orders_service_orders", ["po_type"], unique=False)
    create_index_if_missing(op.f("ix_purchase_orders_service_orders_vendor_id"), "purchase_orders_service_orders", ["vendor_id"], unique=False)
    create_index_if_missing(op.f("ix_purchase_orders_service_orders_po_so_number"), "purchase_orders_service_orders", ["po_so_number"], unique=False)


def downgrade() -> None:
    drop_index_if_present(op.f("ix_purchase_orders_service_orders_po_so_number"), "purchase_orders_service_orders")
    drop_index_if_present(op.f("ix_purchase_orders_service_orders_vendor_id"), "purchase_orders_service_orders")
    drop_index_if_present(op.f("ix_purchase_orders_service_orders_po_type"), "purchase_orders_service_orders")
    drop_table_if_present("purchase_orders_service_orders")

    drop_index_if_present(op.f("ix_vendor_suppliers_vendor_code"), "vendor_suppliers")
    drop_table_if_present("vendor_suppliers")
