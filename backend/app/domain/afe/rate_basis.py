"""Rate-basis classification and planned-quantity derivation for AFE lines.

A catalogue item carries the rate basis it is normally charged on. An AFE line
copies that basis as its default and the planner may override it for that line
only, so a service that is usually charged daily can still be taken as a fixed
lump sum on one particular AFE.

Only ``daily_consumption`` derives a quantity here: consumption per day times
planned days. Everything else (what a *rate* is worth, how contingency and
escalation apply) stays with the costing engine, which is deliberately not
implemented until the business rules are confirmed.
"""

from dataclasses import dataclass
from decimal import Decimal

SERVICE_RATE_BASES: tuple[str, ...] = ("daily", "per_service", "per_section", "fixed")
"""Bases a service may be charged on."""

CONSUMABLE_RATE_BASES: tuple[str, ...] = ("per_unit", "daily_consumption")
"""Bases a mud chemical or cement additive may be charged on."""

RATE_BASES: tuple[str, ...] = SERVICE_RATE_BASES + CONSUMABLE_RATE_BASES

CONSUMABLE_ITEM_TYPES: frozenset[str] = frozenset({"mud_chemical", "cement_additive"})
"""Catalogue item types that are planned as consumption rather than as a service."""

DEFAULT_RATE_BASIS_BY_ITEM_TYPE: dict[str, str] = {
    "service": "daily",
    "tangible": "per_unit",
    "material": "per_unit",
    "equipment": "daily",
    "mud_chemical": "per_unit",
    "cement_additive": "per_unit",
}
"""Basis assumed when the catalogue item does not declare one."""

RATE_BASIS_SYNONYMS: dict[str, str] = {
    "daily_rate": "daily",
    "per_day": "daily",
    "day_rate": "daily",
    "per_section_rate": "per_section",
    "section": "per_section",
    "per_service_rate": "per_service",
    "fixed_rate": "fixed",
    "lump_sum": "fixed",
    "unit": "per_unit",
    "per_unit_rate": "per_unit",
    "daily_usage": "daily_consumption",
    "consumption_per_day": "daily_consumption",
    "per_day_consumption": "daily_consumption",
}


class RateBasisError(ValueError):
    """A rate basis is unknown, or not allowed for the item it was given to."""


def normalize_rate_basis(value: str) -> str:
    """Fold spelling variants ('Daily Rate', 'per-day') onto a canonical basis."""

    raw = value.strip().lower().replace(" ", "_").replace("-", "_")
    return RATE_BASIS_SYNONYMS.get(raw, raw)


def allowed_rate_bases(item_type: str) -> tuple[str, ...]:
    """Bases that make sense for a catalogue item type."""

    if item_type in CONSUMABLE_ITEM_TYPES:
        return CONSUMABLE_RATE_BASES
    if item_type == "service":
        return SERVICE_RATE_BASES
    return ("per_unit", "fixed")


def default_rate_basis(item_type: str, catalogue_basis: str | None = None) -> str:
    """The basis an AFE line starts on: the catalogue item's, else the type default."""

    if catalogue_basis:
        candidate = normalize_rate_basis(catalogue_basis)
        if candidate in allowed_rate_bases(item_type):
            return candidate
    return DEFAULT_RATE_BASIS_BY_ITEM_TYPE.get(item_type, "per_unit")


def validate_rate_basis(item_type: str, rate_basis: str) -> str:
    """Return the canonical basis, or raise if it is not usable for this item type."""

    candidate = normalize_rate_basis(rate_basis)
    allowed = allowed_rate_bases(item_type)
    if candidate not in allowed:
        raise RateBasisError(
            f"rate_basis '{rate_basis}' is not valid for {item_type}; "
            f"use one of {', '.join(allowed)}"
        )
    return candidate


def requires_hole_section(rate_basis: str) -> bool:
    """A per-section charge is meaningless without the section it is charged for."""

    return normalize_rate_basis(rate_basis) == "per_section"


def requires_planned_days(rate_basis: str) -> bool:
    """Daily charges and daily consumption both need a planned duration."""

    return normalize_rate_basis(rate_basis) in {"daily", "daily_consumption"}


@dataclass(frozen=True)
class PlannedQuantity:
    """The quantity an AFE line will be costed on, and where it came from."""

    quantity: Decimal
    computed_quantity: Decimal | None
    is_overridden: bool

    @property
    def source(self) -> str:
        if self.computed_quantity is None:
            return "entered"
        return "overridden" if self.is_overridden else "computed"


def compute_daily_consumption_quantity(
    daily_consumption: Decimal, planned_duration_days: Decimal
) -> Decimal:
    """Total planned consumption = consumption per day x planned days."""

    if daily_consumption < 0 or planned_duration_days < 0:
        raise RateBasisError("daily_consumption and planned_duration_days cannot be negative")
    return daily_consumption * planned_duration_days


def resolve_planned_quantity(
    *,
    rate_basis: str,
    quantity: Decimal | None,
    daily_consumption: Decimal | None,
    planned_duration_days: Decimal | None,
    override_reason: str | None = None,
) -> PlannedQuantity:
    """Derive the line quantity, honouring a reasoned manual override.

    On ``daily_consumption`` the app computes consumption per day times planned
    days. The planner may still type a different quantity, but only with a
    reason recorded against the line — an unexplained mismatch is rejected
    rather than silently accepted.
    """

    basis = normalize_rate_basis(rate_basis)
    if basis != "daily_consumption":
        # AFE lines now define the service scope only; quantities are entered
        # at daily usage/time posting. Preserve historical quantities if sent.
        return PlannedQuantity(quantity=quantity or Decimal("0"), computed_quantity=None, is_overridden=False)

    # Daily usage belongs in the daily cost log. A planned estimate is optional
    # at AFE scope, so an unset value simply leaves the planned quantity at zero.
    if daily_consumption is None or planned_duration_days is None:
        return PlannedQuantity(quantity=quantity or Decimal("0"), computed_quantity=None, is_overridden=False)
    computed = compute_daily_consumption_quantity(daily_consumption, planned_duration_days)
    if quantity is None or quantity == computed:
        return PlannedQuantity(quantity=computed, computed_quantity=computed, is_overridden=False)
    if not (override_reason or "").strip():
        raise RateBasisError(
            f"quantity {quantity} differs from the computed {computed}; "
            "record a quantity_override_reason to keep the override"
        )
    return PlannedQuantity(quantity=quantity, computed_quantity=computed, is_overridden=True)
