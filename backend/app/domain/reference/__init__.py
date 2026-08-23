"""Reference-data registry: the declared sources and dropdown slots.

This package is pure domain code — no FastAPI, no SQLAlchemy. It answers two
questions for the rest of the application:

* *What can a dropdown be fed from?* → :mod:`app.domain.reference.sources`
* *Which dropdowns exist and what may each be bound to?* →
  :mod:`app.domain.reference.slots`

Everything else (persistence of overrides, option resolution, HTTP) is built on
top of these two immutable registries.
"""

from app.domain.reference.slots import (
    SLOTS,
    SLOTS_BY_CODE,
    DropdownSlot,
    get_slot,
    slots_for_module,
)
from app.domain.reference.sources import (
    LABEL_TEMPLATES,
    SOURCES,
    SOURCES_BY_CODE,
    ReferenceSource,
    get_source,
)

__all__ = [
    "LABEL_TEMPLATES",
    "SLOTS",
    "SLOTS_BY_CODE",
    "SOURCES",
    "SOURCES_BY_CODE",
    "DropdownSlot",
    "ReferenceSource",
    "get_slot",
    "get_source",
    "slots_for_module",
]
