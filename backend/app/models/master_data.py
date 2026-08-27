"""Master data models for Unit of Measurements, Currencies, Phases, Activities, Hole Sections, Vendors and PO/SO."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class VendorSupplier(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Vendor / Supplier master data entity."""

    __tablename__ = "vendor_suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vendor_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    purchase_orders: Mapped[list["PurchaseOrderServiceOrder"]] = relationship(
        "PurchaseOrderServiceOrder", back_populates="vendor", lazy="selectin"
    )


class PurchaseOrderServiceOrder(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """Purchase Orders / Service Orders master data entity."""

    __tablename__ = "purchase_orders_service_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    po_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # PO, SO, Callout, Others
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendor_suppliers.id"), nullable=False, index=True)
    po_so_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    is_amendment: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    amendment_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Attachment metadata
    attachment_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attachment_original_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    attachment_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attachment_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    vendor: Mapped["VendorSupplier"] = relationship(
        "VendorSupplier", back_populates="purchase_orders", lazy="joined"
    )
