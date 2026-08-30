"""Well Sub Activities persistence model.

Sub activities break the master-data Activities down into the concrete,
company-assigned steps of one well:

    Rig 1 ──< Well * ──< WellSubActivity * >── 1 Activity (master data)

The entity is **completely well scoped**: the user picks the rig and the well
first and every sub activity entered afterwards belongs to that well. The
``sub_activity_code`` is manual and unique **within the well** (another well
may reuse the same code), enforced by the composite unique constraint.
``activity_id`` points at the stable master-data ``activities`` row, so the
page is controlled by whatever the Master Data page defines as an Activity.
"""

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.models.master_data import Activity, MasterDataSoftDeleteMixin
from app.models.rig_well import Well


class WellSubActivity(Base, TimestampMixin, AuditMixin, MasterDataSoftDeleteMixin):
    """One sub activity of a well, assigned to a responsible party/company.

    ``description`` doubles as the remarks column and is mandatory — the
    sub activity means little without the note describing who does what.
    """

    __tablename__ = "well_sub_activities"
    __table_args__ = (
        UniqueConstraint("well_id", "sub_activity_code", name="uq_well_sub_activities_well_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id"), nullable=False, index=True)
    sub_activity_code: Mapped[str] = mapped_column(String(50), nullable=False)
    sub_activity_name: Mapped[str] = mapped_column(String(150), nullable=False)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False, index=True)
    responsible_party: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    well: Mapped[Well] = relationship("Well", lazy="joined")
    activity: Mapped[Activity] = relationship("Activity", lazy="joined")
