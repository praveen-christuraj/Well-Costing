"""Rig & Well Management persistence models.

The hierarchy is deliberately one-directional and strict, because every
well-scoped transaction will hang off a well and every well hangs off a rig:

    Rig 1 ──< Well * ──< WellSection * ──< WellPhase *

Rigs and Wells are soft-deleteable business entities (``is_deleted`` /
``deleted_at``) so deleted rows move to a "Deleted Entries" tab and can be
restored or permanently removed. Sections and phases belong to a well's
*configuration*; they are replaced wholesale when a configuration is saved
(no independent lifecycle) and are cascade-removed when a well is permanently
deleted.
"""

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.master_data import HoleSection, MasterDataSoftDeleteMixin, Phase


class Rig(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """A drilling rig. Wells are created under a rig."""

    __tablename__ = "rigs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rig_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    rig_name: Mapped[str] = mapped_column(String(200), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    wells: Mapped[list["Well"]] = relationship(
        "Well", back_populates="rig", lazy="selectin", cascade="all, delete-orphan"
    )


class Well(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """A well scoped to a rig.

    ``status`` tracks the well lifecycle (``active`` until the well is completed;
    ``completed`` once done) and ``config_status`` tracks whether the well's
    section/phase configuration is a mutable ``draft`` or a frozen ``configured``
    snapshot.
    """

    __tablename__ = "wells"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rig_id: Mapped[int] = mapped_column(ForeignKey("rigs.id"), nullable=False, index=True)
    well_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    well_name: Mapped[str] = mapped_column(String(200), nullable=False)
    well_location: Mapped[str] = mapped_column(String(300), nullable=False)
    block: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False, index=True
    )  # active | completed
    config_status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", nullable=False, index=True
    )  # draft | configured
    # Unit chosen for this well's depth figures (metre or feet). Stored once at
    # the well level; sections inherit it for reporting.
    depth_unit: Mapped[str] = mapped_column(
        String(10), default="m", server_default="m", nullable=False
    )

    rig: Mapped[Rig] = relationship("Rig", back_populates="wells", lazy="joined")

    sections: Mapped[list["WellSection"]] = relationship(
        "WellSection",
        back_populates="well",
        lazy="selectin",
        order_by="WellSection.sort_order",
        cascade="all, delete-orphan",
    )


class WellSection(Base, TimestampMixin, AuditMixin):
    """One hole section configured for a well, with from/to depth.

    Depth is recorded in a single unit per well configuration (metre or feet).
    ``to_depth`` of the last section is the well's total depth.
    """

    __tablename__ = "well_sections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id"), nullable=False, index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("hole_sections.id"), nullable=False, index=True)
    from_depth: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    to_depth: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    well: Mapped[Well] = relationship("Well", back_populates="sections", lazy="joined")

    section: Mapped[HoleSection] = relationship("HoleSection", lazy="joined")

    phases: Mapped[list["WellPhase"]] = relationship(
        "WellPhase",
        back_populates="section",
        lazy="selectin",
        order_by="WellPhase.sort_order",
        cascade="all, delete-orphan",
    )


class WellPhase(Base, TimestampMixin, AuditMixin):
    """One phase configured inside a well section, with a decimal day count."""

    __tablename__ = "well_phases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("well_sections.id"), nullable=False, index=True)
    phase_id: Mapped[int] = mapped_column(ForeignKey("phases.id"), nullable=False, index=True)
    days: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    section: Mapped[WellSection] = relationship("WellSection", back_populates="phases", lazy="joined")

    phase: Mapped[Phase] = relationship("Phase", lazy="joined")
