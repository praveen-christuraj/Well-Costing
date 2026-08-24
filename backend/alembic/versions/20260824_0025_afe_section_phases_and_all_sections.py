"""Add AFE section phase rows and the 'applies to all sections' line flag.

A section is now a container defined by hole section and depth interval; its
operational phases live in the new ``afe_section_phases`` table and the
section's ``planned_days`` is derived as the sum of its phases. AFE lines also
gain ``applies_to_all_sections`` so a common service rate can be entered once
and apply to every section of the AFE.

Revision ID: 20260824_0025
Revises: 20260823_0024
Create Date: 2026-08-24 10:00:00.000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0025"
down_revision: str | None = "20260823_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "afe_section_phases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("afe_section_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), server_default="1", nullable=False),
        sa.Column("phase", sa.String(length=100), server_default="Drilling", nullable=False),
        sa.Column("planned_days", sa.Numeric(12, 4), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["afe_section_id"],
            ["afe_sections.id"],
            ondelete="CASCADE",
            name="fk_afe_section_phases_afe_section_id",
        ),
        sa.CheckConstraint("sequence >= 1", name="positive_afe_section_phase_sequence"),
        sa.CheckConstraint("planned_days >= 0", name="non_negative_afe_section_phase_days"),
    )
    op.create_index(
        "ix_afe_section_phases_afe_section_id", "afe_section_phases", ["afe_section_id"]
    )
    op.create_index("ix_afe_section_phases_phase", "afe_section_phases", ["phase"])
    op.create_index("ix_afe_section_phases_is_active", "afe_section_phases", ["is_active"])

    op.add_column(
        "afe_lines",
        sa.Column(
            "applies_to_all_sections",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_afe_lines_applies_to_all_sections",
        "afe_lines",
        ["applies_to_all_sections"],
    )


def downgrade() -> None:
    op.drop_index("ix_afe_lines_applies_to_all_sections", table_name="afe_lines")
    op.drop_column("afe_lines", "applies_to_all_sections")
    op.drop_index("ix_afe_section_phases_is_active", table_name="afe_section_phases")
    op.drop_index("ix_afe_section_phases_phase", table_name="afe_section_phases")
    op.drop_index("ix_afe_section_phases_afe_section_id", table_name="afe_section_phases")
    op.drop_table("afe_section_phases")
