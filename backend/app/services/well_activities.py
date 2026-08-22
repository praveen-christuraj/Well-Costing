"""Well-scoped sub-activity management.

After creating a well, the user configures sub-activities (e.g. Planned,
NPT-1, NPT-2, UPA-1, UPA-2) linked to a primary activity from master data.
Each sub-activity has a responsible party for cost accountability.
"""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.models.categories import Activity, WellActivity


class WellActivityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    well_id: UUID
    activity_id: UUID
    name: str = Field(min_length=1, max_length=255)
    responsible_party: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_active: bool = True


class WellActivityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    responsible_party: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class WellActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    well_id: UUID
    activity_id: UUID
    activity_code: str | None = None
    activity_name: str | None = None
    name: str
    responsible_party: str | None
    description: str | None
    is_active: bool
    created_at: str
    updated_at: str


class WellActivityService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session = session
        self.actor_id = actor_id

    def list_for_well(self, well_id: UUID) -> list[WellActivityRead]:
        stmt = (
            select(WellActivity)
            .where(WellActivity.well_id == well_id)
            .order_by(WellActivity.name)
        )
        rows = self.session.execute(stmt).scalars().all()
        return [self._serialize(r) for r in rows]

    def create(self, payload: WellActivityCreate) -> WellActivityRead:
        if self.session.get(Activity, payload.activity_id) is None:
            raise BusinessValidationError("activity_id does not reference an existing activity")
        existing = self.session.execute(
            select(WellActivity).where(
                WellActivity.well_id == payload.well_id,
                WellActivity.name == payload.name,
            )
        ).scalar_one_or_none()
        if existing:
            raise ConflictError(
                f"A sub-activity named '{payload.name}' already exists for this well"
            )
        record = WellActivity(
            id=uuid4(),
            well_id=payload.well_id,
            activity_id=payload.activity_id,
            name=payload.name.strip(),
            responsible_party=payload.responsible_party,
            description=payload.description,
            is_active=payload.is_active,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(record)
        self.session.flush()
        self.session.commit()
        self.session.refresh(record)
        return self._serialize(record)

    def update(self, item_id: UUID, payload: WellActivityUpdate) -> WellActivityRead:
        record = self.session.get(WellActivity, item_id)
        if record is None:
            raise NotFoundError("Well activity not found")
        values = payload.model_dump(exclude_unset=True)
        if "activity_id" in values and values["activity_id"] is not None:
            if self.session.get(Activity, values["activity_id"]) is None:
                raise BusinessValidationError(
                    "activity_id does not reference an existing activity"
                )
        for field, value in values.items():
            if field == "name" and value is not None:
                value = value.strip()
            setattr(record, field, value)
        record.updated_by = self.actor_id
        self.session.flush()
        self.session.commit()
        self.session.refresh(record)
        return self._serialize(record)

    def delete(self, item_id: UUID) -> None:
        record = self.session.get(WellActivity, item_id)
        if record is None:
            raise NotFoundError("Well activity not found")
        self.session.delete(record)
        self.session.flush()
        self.session.commit()

    @staticmethod
    def _serialize(record: WellActivity) -> WellActivityRead:
        return WellActivityRead(
            id=record.id,
            well_id=record.well_id,
            activity_id=record.activity_id,
            activity_code=record.activity.code if record.activity else None,
            activity_name=record.activity.name if record.activity else None,
            name=record.name,
            responsible_party=record.responsible_party,
            description=record.description,
            is_active=record.is_active,
            created_at=record.created_at.isoformat() if record.created_at else "",
            updated_at=record.updated_at.isoformat() if record.updated_at else "",
        )
