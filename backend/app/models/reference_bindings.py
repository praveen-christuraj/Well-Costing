"""Configurable binding between a dropdown in the UI and its master-data source.

Every picker in the application is a *slot* — a stable, code-named place in the
UI such as ``afe.line.secondary_category`` or ``daily_cost.service_item``. The
slot catalogue itself is declared in code (``app.domain.reference.slots``) so it
is versioned and reviewable; what a super administrator configures here is only
*which* registered source feeds that slot, with which fixed filters and label
format.

That split is deliberate. The registry of slots and sources is the backbone the
rest of the application programs against, so it cannot drift with data entry;
the binding row is the small, audited piece of configuration on top of it.
"""

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, TimestampMixin


class DropdownBinding(TimestampMixin, AuditMixin, Base):
    """A super-admin override of the default source for one dropdown slot."""

    __tablename__ = "dropdown_bindings"
    __table_args__ = (UniqueConstraint("slot_code", name="uq_dropdown_bindings_slot_code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slot_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source_code: Mapped[str] = mapped_column(String(120), index=True)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    label_template: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sort_by: Mapped[str | None] = mapped_column(String(60), nullable=True)
    include_inactive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )
