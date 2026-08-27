"""Master data models for Unit of Measurements, Currencies, Phases, Activities, and Hole Sections."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, TimestampMixin


class MasterDataSoftDeleteMixin:
    """Soft delete fields for master data records."""

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UnitOfMeasurement(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Unit of Measurement (UOM) master data entity."""

    __tablename__ = "uom"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    unit_name: Mapped[str] = mapped_column(String(150), nullable=False)
    unit_symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Currency(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Currency master data entity."""

    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    currency_code: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    currency_name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Phase(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Drilling Phase master data entity."""

    __tablename__ = "phases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phase_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    phase_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Activity(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Activity master data entity."""

    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    activity_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    activity_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class HoleSection(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Hole Section master data entity."""

    __tablename__ = "hole_sections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    section_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    section_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
