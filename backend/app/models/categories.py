"""Category hierarchy, activity master data, and well-scoped sub-activities.

The three-level category hierarchy (Primary → Secondary → Tertiary) replaces the
hardcoded ``applies_to`` values that previously drove item classification.
Activities (Planned, NPT, UPA) are master-data rows; well activities are the
well-scoped sub-activities that link each daily cost entry to a responsible
party for cost accountability.
"""

from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin


class PrimaryCategory(TimestampMixin, AuditMixin, Base):
    """Top-level configurable classification — replaces hardcoded applies_to values.

    Examples: Drilling, Services, Tangibles, Consumables. Every secondary
    category belongs to exactly one primary category.
    """

    __tablename__ = "primary_categories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_primary_categories_code"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    secondaries: Mapped[list["SecondaryCategory"]] = relationship(
        back_populates="primary_category", lazy="selectin"
    )


class SecondaryCategory(TimestampMixin, AuditMixin, Base):
    """Second-level classification linked to a primary category.

    Examples: Under Drilling → Rig Operations, Mud Systems. Under Services →
    Cementing, Directional Drilling. Cost categories pick their parent from
    this level.
    """

    __tablename__ = "secondary_categories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_secondary_categories_code"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )
    primary_category_id: Mapped[UUID] = mapped_column(
        ForeignKey("primary_categories.id", ondelete="RESTRICT"), index=True
    )

    primary_category: Mapped[PrimaryCategory] = relationship(
        back_populates="secondaries", lazy="joined"
    )
    tertiaries: Mapped[list["TertiaryCategory"]] = relationship(
        back_populates="secondary_category", lazy="selectin"
    )


class TertiaryCategory(TimestampMixin, AuditMixin, Base):
    """Third-level classification linked to a secondary category.

    Auto-links to its primary category through the secondary parent.
    Examples: Under Rig Operations → Hoisting, Rotating, Circulating.
    """

    __tablename__ = "tertiary_categories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_tertiary_categories_code"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )
    secondary_category_id: Mapped[UUID] = mapped_column(
        ForeignKey("secondary_categories.id", ondelete="RESTRICT"), index=True
    )

    secondary_category: Mapped[SecondaryCategory] = relationship(
        back_populates="tertiaries", lazy="joined"
    )

    @property
    def primary_category(self) -> PrimaryCategory | None:
        """Auto-resolved through the secondary parent."""
        return (
            self.secondary_category.primary_category
            if self.secondary_category
            else None
        )


class Activity(TimestampMixin, AuditMixin, Base):
    """Master-data activity classification: Planned, NPT, UPA.

    Each daily cost entry and service line is tagged with a sub-activity that
    ultimately rolls up to one of these three primary activities for reporting.
    """

    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint("code", name="uq_activities_code"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    well_activities: Mapped[list["WellActivity"]] = relationship(
        back_populates="activity", lazy="selectin"
    )


class WellActivity(TimestampMixin, AuditMixin, Base):
    """Well-scoped sub-activity linked to a primary activity.

    After creating a well, the user configures sub-activities such as
    Planned, NPT-1, NPT-2, UPA-1, UPA-2. Each sub-activity belongs to a
    responsible party; costs posted against it are accounted to that party.
    """

    __tablename__ = "well_activities"
    __table_args__ = (
        UniqueConstraint("well_id", "name", name="uq_well_activities_well_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    well_id: Mapped[UUID] = mapped_column(
        ForeignKey("wells.id", ondelete="CASCADE"), index=True
    )
    activity_id: Mapped[UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    responsible_party: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    activity: Mapped[Activity] = relationship(back_populates="well_activities", lazy="joined")
