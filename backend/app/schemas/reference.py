"""Schemas for the configurable dropdown registry."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReferenceSourceRead(BaseModel):
    """A source a dropdown may be bound to."""

    code: str
    label: str
    kind: str
    entity: str | None = None
    description: str = ""
    parent_field: str | None = None
    parent_source: str | None = None
    filterable: list[str] = Field(default_factory=lambda: list[str]())


class DropdownBindingRead(BaseModel):
    """The stored override for a slot, when one exists."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slot_code: str
    source_code: str
    filters: dict[str, Any] = Field(default_factory=lambda: dict[str, Any]())
    label_template: str | None = None
    sort_by: str | None = None
    include_inactive: bool = False
    notes: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None = None
    updated_by: UUID | None = None


class DropdownBindingWrite(BaseModel):
    """Super-admin change to where a dropdown reads from."""

    model_config = ConfigDict(extra="forbid")

    source_code: str = Field(min_length=1, max_length=120)
    filters: dict[str, Any] = Field(default_factory=lambda: dict[str, Any]())
    label_template: str | None = Field(default=None, max_length=120)
    sort_by: str | None = Field(default=None, max_length=60)
    include_inactive: bool = False
    notes: str | None = None


class DropdownSlotRead(BaseModel):
    """A dropdown in the UI together with the source currently feeding it."""

    code: str
    module: str
    label: str
    description: str
    default_source: str
    allowed_sources: list[str] = Field(default_factory=lambda: list[str]())
    cascades_from: str | None = None
    locked: bool = False
    #: Source in effect right now — the override when set, otherwise the default.
    effective_source: str
    is_overridden: bool = False
    binding: DropdownBindingRead | None = None
    label_template: str = "{code} — {name}"
    filters: dict[str, Any] = Field(default_factory=lambda: dict[str, Any]())


class DropdownRegistryRead(BaseModel):
    """Everything the super-admin console needs in one call."""

    modules: list[dict[str, str]]
    sources: list[ReferenceSourceRead]
    slots: list[DropdownSlotRead]


class ReferenceOption(BaseModel):
    """One selectable option."""

    value: str
    label: str
    code: str | None = None
    name: str | None = None
    #: Parent key so the client can cascade without a second round trip.
    parent_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=lambda: dict[str, Any]())


class ReferenceOptionsRead(BaseModel):
    """Resolved options for one slot."""

    slot: str
    source: str
    total: int
    options: list[ReferenceOption]
