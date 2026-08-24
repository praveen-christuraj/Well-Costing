"""Well-scoped sub-activity management.

After creating a well, the user configures sub-activities (e.g. Planned,
NPT-1, NPT-2, UPA-1, UPA-2) linked to a primary activity from master data.
Each sub-activity has a responsible party for cost accountability.

Well activities follow the same audited lifecycle as the other application
records: create/update, soft delete, and recover.  A physical delete would
break the audit trail and would also invalidate daily-cost history, so the
DELETE endpoint deliberately deactivates the row instead.
"""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.models.afe import Well
from app.models.categories import Activity, WellActivity
from app.services.audit import log_entity_action


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

    def list_for_well(
        self, well_id: UUID, *, include_inactive: bool = False
    ) -> list[WellActivityRead]:
        """Return the well's active activities, or its full recovery list."""

        well = self.session.get(Well, well_id)
        if well is None:
            raise NotFoundError("Well not found")
        statement = select(WellActivity).where(WellActivity.well_id == well_id)
        if not include_inactive:
            statement = statement.where(WellActivity.is_active.is_(True))
        rows = self.session.execute(statement.order_by(WellActivity.name)).scalars().all()
        return [self._serialize(r) for r in rows]

    def create(self, payload: WellActivityCreate) -> WellActivityRead:
        well = self.session.get(Well, payload.well_id)
        if well is None or not well.is_active:
            raise BusinessValidationError("well_id must reference an active well")
        activity = self.session.get(Activity, payload.activity_id)
        if activity is None or not activity.is_active:
            raise BusinessValidationError(
                "activity_id must reference an active activity from master data"
            )
        name = payload.name.strip()
        existing = self.session.execute(
            select(WellActivity).where(
                WellActivity.well_id == payload.well_id,
                WellActivity.name == name,
            )
        ).scalar_one_or_none()
        if existing:
            if not existing.is_active:
                raise ConflictError(
                    f"A deleted sub-activity named '{name}' already exists for this well. "
                    "Recover it instead of creating a duplicate."
                )
            raise ConflictError(f"A sub-activity named '{name}' already exists for this well")
        record = WellActivity(
            id=uuid4(),
            well_id=payload.well_id,
            activity_id=payload.activity_id,
            name=name,
            responsible_party=payload.responsible_party,
            description=payload.description,
            is_active=payload.is_active,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(record)
        self.session.flush()
        self._audit(
            "create",
            record,
            {
                "well_id": str(record.well_id),
                "activity_id": str(record.activity_id),
                "name": record.name,
                "responsible_party": record.responsible_party,
                "description": record.description,
            },
        )
        self.session.commit()
        self.session.refresh(record)
        return self._serialize(record)

    def update(self, item_id: UUID, payload: WellActivityUpdate) -> WellActivityRead:
        record = self.session.get(WellActivity, item_id)
        if record is None:
            raise NotFoundError("Well activity not found")
        values = payload.model_dump(exclude_unset=True)
        activity_id = values.get("activity_id")
        if "activity_id" in values and activity_id is not None:
            activity = self.session.get(Activity, activity_id)
            if activity is None or not activity.is_active:
                raise BusinessValidationError(
                    "activity_id must reference an active activity from master data"
                )
        if "name" in values and values["name"] is not None:
            values["name"] = str(values["name"]).strip()
            clash = self.session.scalar(
                select(WellActivity).where(
                    WellActivity.well_id == record.well_id,
                    WellActivity.name == values["name"],
                    WellActivity.id != record.id,
                )
            )
            if clash:
                raise ConflictError(
                    f"A sub-activity named '{values['name']}' already exists for this well"
                )
        previous = self._snapshot(record)
        for field, value in values.items():
            setattr(record, field, value)
        record.updated_by = self.actor_id
        self.session.flush()
        if previous["is_active"] and record.is_active is False:
            action = "soft_delete"
        elif not previous["is_active"] and record.is_active:
            action = "recover"
        else:
            action = "update"
        self._audit(action, record, {"before": previous, "after": self._snapshot(record)})
        self.session.commit()
        self.session.refresh(record)
        return self._serialize(record)

    def delete(self, item_id: UUID) -> None:
        """Soft-delete a sub-activity while preserving references and auditability."""

        record = self.session.get(WellActivity, item_id)
        if record is None:
            raise NotFoundError("Well activity not found")
        if not record.is_active:
            raise BusinessValidationError("Well activity is already deleted")
        before = self._snapshot(record, active=True)
        record.is_active = False
        record.updated_by = self.actor_id
        self.session.flush()
        self._audit(
            "soft_delete",
            record,
            {"before": before, "after": self._snapshot(record)},
        )
        self.session.commit()

    def recover(self, item_id: UUID) -> WellActivityRead:
        record = self.session.get(WellActivity, item_id)
        if record is None:
            raise NotFoundError("Well activity not found")
        if record.is_active:
            raise BusinessValidationError("Well activity is not deleted and cannot be recovered")
        clash = self.session.scalar(
            select(WellActivity).where(
                WellActivity.well_id == record.well_id,
                WellActivity.name == record.name,
                WellActivity.is_active.is_(True),
                WellActivity.id != record.id,
            )
        )
        if clash:
            raise ConflictError(
                f"A sub-activity named '{record.name}' is already active for this well"
            )
        before = self._snapshot(record)
        record.is_active = True
        record.updated_by = self.actor_id
        self.session.flush()
        self._audit(
            "recover",
            record,
            {"before": before, "after": self._snapshot(record)},
        )
        self.session.commit()
        self.session.refresh(record)
        return self._serialize(record)

    def _audit(
        self,
        action: str,
        record: WellActivity,
        details: dict[str, object] | None,
    ) -> None:
        log_entity_action(
            self.session,
            self.actor_id,
            action,
            "well_activity",
            entity_id=record.id,
            entity_code=record.name,
            details={"well_id": str(record.well_id), **(details or {})},
        )

    @staticmethod
    def _snapshot(record: WellActivity, *, active: bool | None = None) -> dict[str, object]:
        return {
            "activity_id": str(record.activity_id),
            "name": record.name,
            "responsible_party": record.responsible_party,
            "description": record.description,
            "is_active": record.is_active if active is None else active,
        }

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
