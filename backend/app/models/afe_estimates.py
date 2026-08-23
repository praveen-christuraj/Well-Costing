"""AFE Cost Estimate models — well-scoped unit rates for AFE lines.

The AFE (scope: services, chemicals, additives, tangibles, quantities) and the
AFE Cost Estimate (the unit rate the well negotiated for each of those lines)
together form the financial backbone of the well:

* The AFE page defines *what* is planned for the well.
* The AFE Cost Estimate page prices *each AFE line* with a well-scoped unit
  rate. Nothing is priced that is not in the AFE.
* Daily cost entries read their unit rates from the AFE Cost Estimate only,
  with a per-line override (recorded with the entry) for exceptional days.

One estimate rate row exists per AFE line. Rates are keyed to the AFE line —
not the catalogue item — so a service priced differently per hole section on
two AFE lines keeps two rates.
"""

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.afe import Afe, AfeLine
from app.models.master_data import Vendor


class AfeCostEstimateLine(TimestampMixin, AuditMixin, Base):
    """Well-scoped unit rate for one AFE line."""

    __tablename__ = "afe_cost_estimate_lines"
    __table_args__ = (
        UniqueConstraint("afe_line_id", name="uq_afe_cost_estimate_lines_afe_line"),
        CheckConstraint("unit_rate >= 0", name="non_negative_estimate_unit_rate"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    afe_id: Mapped[UUID] = mapped_column(ForeignKey("afes.id", ondelete="CASCADE"), index=True)
    afe_line_id: Mapped[UUID] = mapped_column(
        ForeignKey("afe_lines.id", ondelete="CASCADE"), index=True
    )
    unit_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )

    afe: Mapped[Afe] = relationship(lazy="joined")
    afe_line: Mapped[AfeLine] = relationship(lazy="joined")
    vendor: Mapped[Vendor | None] = relationship(lazy="joined")
