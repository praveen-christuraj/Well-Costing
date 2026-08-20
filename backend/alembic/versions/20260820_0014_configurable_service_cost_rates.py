"""configure hole sections and service costing rate bases

Revision ID: 20260820_0014
Revises: 20260816_0013
"""
from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "20260820_0014"
down_revision: str | None = "20260816_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hole_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hole_sections")),
        sa.UniqueConstraint("code", name=op.f("uq_hole_sections_code")),
    )
    op.create_index(op.f("ix_hole_sections_code"), "hole_sections", ["code"], unique=True)
    op.create_index(op.f("ix_hole_sections_name"), "hole_sections", ["name"])
    op.create_index(op.f("ix_hole_sections_is_active"), "hole_sections", ["is_active"])
    op.drop_index(op.f("ix_service_rate_cards_hole_section"), table_name="service_rate_cards")
    op.drop_index(op.f("ix_service_rate_cards_service_order_id"), table_name="service_rate_cards")
    with op.batch_alter_table("service_rate_cards") as batch:
        batch.drop_constraint(
            op.f("fk_service_rate_cards_service_order_id_service_orders"),
            type_="foreignkey",
        )
        batch.add_column(sa.Column("hole_section_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("rate_basis", sa.String(20), server_default="daily", nullable=False))
        batch.add_column(sa.Column("personnel_operating_rate", sa.Numeric(18, 4), server_default="0", nullable=False))
        batch.add_column(sa.Column("personnel_standby_rate", sa.Numeric(18, 4), server_default="0", nullable=False))
        batch.add_column(sa.Column("other_rate", sa.Numeric(18, 4), server_default="0", nullable=False))
        batch.create_foreign_key(op.f("fk_service_rate_cards_hole_section_id_hole_sections"), "hole_sections", ["hole_section_id"], ["id"], ondelete="RESTRICT")
        batch.create_check_constraint("valid_service_rate_basis", "rate_basis IN ('daily','per_service','per_section','fixed')")
        batch.drop_constraint("non_negative_service_rates", type_="check")
        batch.create_check_constraint("non_negative_service_rates", "operating_rate >= 0 AND standby_rate >= 0 AND mobilisation_rate >= 0 AND demobilisation_rate >= 0 AND personnel_operating_rate >= 0 AND personnel_standby_rate >= 0 AND other_rate >= 0")

    # Preserve existing free-text sections by promoting each distinct value into
    # the new configuration table and linking its historical rate cards.
    connection = op.get_bind()
    sections = connection.execute(
        sa.text("SELECT DISTINCT hole_section FROM service_rate_cards "
                "WHERE hole_section IS NOT NULL AND TRIM(hole_section) <> ''")
    ).scalars()
    configured: dict[str, object] = {}
    for section in sections:
        code = str(section).strip().upper()
        section_id = configured.get(code)
        if section_id is None:
            section_id = uuid4()
            configured[code] = section_id
            connection.execute(
                sa.text("INSERT INTO hole_sections (id, code, name) "
                        "VALUES (:id, :code, :name)"),
                {"id": section_id, "code": code, "name": str(section).strip()},
            )
        connection.execute(
            sa.text("UPDATE service_rate_cards SET hole_section_id = :id "
                    "WHERE hole_section = :section"),
            {"id": section_id, "section": section},
        )

    with op.batch_alter_table("service_rate_cards") as batch:
        batch.drop_column("hole_section")
        batch.drop_column("service_order_id")
    op.create_index(op.f("ix_service_rate_cards_hole_section_id"), "service_rate_cards", ["hole_section_id"])
    op.create_index(op.f("ix_service_rate_cards_rate_basis"), "service_rate_cards", ["rate_basis"])


def downgrade() -> None:
    with op.batch_alter_table("service_rate_cards") as batch:
        batch.add_column(sa.Column("service_order_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("hole_section", sa.String(60), nullable=True))
        batch.drop_constraint("non_negative_service_rates", type_="check")
        batch.create_check_constraint("non_negative_service_rates", "operating_rate >= 0 AND standby_rate >= 0 AND mobilisation_rate >= 0 AND demobilisation_rate >= 0")
        batch.drop_constraint("valid_service_rate_basis", type_="check")
        batch.drop_column("other_rate")
        batch.drop_column("personnel_standby_rate")
        batch.drop_column("personnel_operating_rate")
        batch.drop_column("rate_basis")
        batch.drop_column("hole_section_id")
    op.drop_table("hole_sections")
