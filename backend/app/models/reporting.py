"""Audited report/export runs while financial metric policy remains pending."""

from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, TimestampMixin


class ReportExportAttempt(TimestampMixin, AuditMixin, Base):
    __tablename__ = "report_export_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('completed_shell','blocked','failed')", name="valid_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    report_code: Mapped[str] = mapped_column(String(100), index=True)
    policy_version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), index=True)
    filters_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)
    row_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
