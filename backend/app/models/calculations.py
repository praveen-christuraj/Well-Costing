"""Phase 5 calculation audit records; numeric results remain pending confirmed rules."""

from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.estimates import EstimateVersion


class EstimateCalculation(TimestampMixin, AuditMixin, Base):
    __tablename__ = "estimate_calculations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started','completed','blocked','failed')",
            name="valid_status",
        ),
        Index("ix_estimate_calculations_version_created", "estimate_version_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    estimate_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("estimate_versions.id", ondelete="CASCADE"), index=True
    )
    engine_version: Mapped[str] = mapped_column(String(50))
    rule_set_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    output_snapshot: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)

    estimate_version: Mapped[EstimateVersion] = relationship(lazy="joined")
