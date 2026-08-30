"""Daily cost calculation engine.

The daily cost page is the operational counterpart of the AFE: the AFE plans
the money, this engine prices what was actually spent on one rig + well + date.
Like :mod:`app.domain.afe_costing` it is deliberately framework-free (no
FastAPI / SQLAlchemy / Pydantic) and *pure*, so every money rule can be
unit-tested with plain dataclasses.

Rules implemented here
----------------------

1. **The rate card comes from the AFE.** A service carries the charging basis
   (``Daily Rate`` / ``Per Service Rate`` / ``Per Section Rate``) and the unit
   rate the AFE configured for it. Daily costs read the unit rate of the
   *relevant* charge category — Mobilization, Demobilization, Operation,
   Standby, Personnel-Operation, Personnel-Standby, Fixed Charge or Others —
   not the AFE's Operation price.
2. **Daily Rate** services are charged ``days x unit rate``. The quantity may
   be entered in hours (0-24, decimals allowed) — converted with ``/24`` — or
   in decimal days (0-1), matching the AFE charge lines.
3. **Mobilization, Demobilization and Fixed Charge are one-time amounts**: the
   entered hours/days never multiply them, the whole configured amount is
   charged once. (The quantity is still recorded so the day sheet shows what
   the user typed.)
4. **Per Service Rate** services charge the price allotted to that service —
   the quantity is recorded for information but does not scale the amount.
5. **Per Section Rate** services charge the amount the AFE configured for the
   selected section (and, when given, that phase).
6. **Scope is recorded on every line** — Section and Phase come from the well
   configuration (Master Data ids) and the Well Sub Activity comes from the
   Well Sub Activities page — so the same service can appear several times on
   one day against different sub activities and different charge categories
   without the amounts interfering.
7. **Override unit rate** bypasses the captured AFE rate, exactly like the AFE
   page's override.
8. **Consumables** cost ``usage x unit rate``: mud chemicals and drill bits
   take the item rate captured from the AFE / Master Data, fuel takes the rate
   captured on the AFE cost estimate, and cement additives are entered as a
   manual total for the chosen section / phase / sub activity.
9. **Tangibles** cost ``quantity x unit rate`` (override wins) and are entered
   as a block at the end of the well, never per day of drilling.

Rounding follows the AFE engine: money to 2 decimals, day quantities to 4
decimals, and rollups are summed from the already-rounded line amounts so the
printed daily report always adds up.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.afe_costing import (
    BASIS_DAILY,
    BASIS_PER_SECTION,
    BASIS_PER_SERVICE,
    CHARGE_CATEGORIES,
    CHARGING_BASES,
    DAY_BASED_CATEGORIES,
    GROUP_CONSUMABLES,
    GROUP_SERVICES,
    GROUP_TANGIBLES,
    ONE_TIME_CATEGORIES,
    UNIT_DAYS,
    UNIT_HOURS,
    days_from_quantity,
    effective_rate,
    money,
    normalize_basis,
    normalize_category,
    normalize_unit,
    to_decimal,
)

__all__ = [
    "BASIS_DAILY",
    "BASIS_PER_SECTION",
    "BASIS_PER_SERVICE",
    "CEMENT_ADDITIVE",
    "CHARGE_CATEGORIES",
    "CHARGING_BASES",
    "CONSUMABLE_CATEGORIES",
    "CONSUMABLE_CATEGORY_LABELS",
    "DAILY_COST_STATUSES",
    "DAY_BASED_CATEGORIES",
    "DRILL_BIT",
    "FUEL",
    "GROUP_CONSUMABLES",
    "GROUP_SERVICES",
    "GROUP_TANGIBLES",
    "MUD_CHEMICAL",
    "ONE_TIME_CATEGORIES",
    "QUANTITY_UNITS",
    "RECONCILIATION_STATUSES",
    "STATUS_DRAFT",
    "STATUS_SUBMITTED",
    "DailyConsumableLine",
    "DailyCostTotals",
    "DailyServiceLine",
    "DailyTangibleLine",
    "LineResult",
    "RateCardEntry",
    "SectionRateEntry",
    "compile_daily_cost",
    "consumable_amount",
    "is_one_time_category",
    "normalize_consumable_category",
    "service_amount",
    "tangible_amount",
    "validate_quantity",
]

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

MUD_CHEMICAL = "mud_chemical"
FUEL = "fuel"
CEMENT_ADDITIVE = "cement_additive"
DRILL_BIT = "drill_bit"

#: The four consumable categories of the daily cost page. None of them is
#: mandatory — whichever was consumed on the day is entered.
CONSUMABLE_CATEGORIES: tuple[str, ...] = (MUD_CHEMICAL, FUEL, CEMENT_ADDITIVE, DRILL_BIT)

CONSUMABLE_CATEGORY_LABELS: Mapping[str, str] = {
    MUD_CHEMICAL: "Mud Chemicals",
    FUEL: "Fuel",
    CEMENT_ADDITIVE: "Cement Additives",
    DRILL_BIT: "Drill Bits",
}

#: Categories whose item comes from a Master Data / catalogue list. The other
#: two (fuel, cement additives) are rate-from-AFE / manual-total kinds.
CATALOGUE_CONSUMABLE_KINDS: tuple[str, ...] = (MUD_CHEMICAL, DRILL_BIT)

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
DAILY_COST_STATUSES: tuple[str, ...] = (STATUS_DRAFT, STATUS_SUBMITTED)

#: The reconciliation middle layer that sits between the daily actuals and the
#: AFE comparison. It is intentionally declared here already so the daily cost
#: rows carry the hooks the (later) reconciliation module needs without a
#: second migration: a weekly — or whenever-required — reconciliation run
#: stamps the period, the actor and the timestamp onto the entries it covers.
RECONCILIATION_PENDING = "pending"
RECONCILIATION_RECONCILED = "reconciled"
RECONCILIATION_STATUSES: tuple[str, ...] = (RECONCILIATION_PENDING, RECONCILIATION_RECONCILED)

QUANTITY_UNITS: tuple[str, ...] = (UNIT_DAYS, UNIT_HOURS)

#: Hours may run 0-24 on a day; days are a fraction of one day, so 0-1.
MAX_HOURS = Decimal("24")
MAX_DAYS = Decimal("1")

_CONSUMABLE_LOOKUP: dict[str, str] = {
    # Keys are stored already folded (lower-case, no spaces/underscores/hyphens)
    # so "Mud Chemicals", "mud_chemical" and "MUD-CHEMICAL" all resolve.
    "mudchemical": MUD_CHEMICAL,
    "mudchemicals": MUD_CHEMICAL,
    "chemical": MUD_CHEMICAL,
    "chemicals": MUD_CHEMICAL,
    "fuel": FUEL,
    "fuels": FUEL,
    "diesel": FUEL,
    "cement": CEMENT_ADDITIVE,
    "cementadditive": CEMENT_ADDITIVE,
    "cementadditives": CEMENT_ADDITIVE,
    "additive": CEMENT_ADDITIVE,
    "additives": CEMENT_ADDITIVE,
    "bit": DRILL_BIT,
    "bits": DRILL_BIT,
    "drillbit": DRILL_BIT,
    "drillbits": DRILL_BIT,
}


def normalize_consumable_category(value: object) -> str:
    """Map a user/import label onto one of the four consumable categories."""

    key = str(value or "").strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    canonical = _CONSUMABLE_LOOKUP.get(key)
    if canonical is not None:
        return canonical
    raise ValueError(
        f"Unknown consumable category '{value}' — expected one of "
        "Mud Chemicals, Fuel, Cement Additives or Drill Bits"
    )


def is_one_time_category(category: object) -> bool:
    """True for Mobilization / Demobilization / Fixed Charge (never multiplied)."""

    try:
        return normalize_category(category) in ONE_TIME_CATEGORIES
    except ValueError:
        return str(category or "").strip() in ONE_TIME_CATEGORIES


def validate_quantity(quantity: object, unit: object) -> Decimal:
    """Validate an entered operating quantity and return the raw number.

    Hours must fall in ``0-24`` and days in ``0-1`` — both accept decimals
    (``7.5`` hours, ``0.25`` days). Anything else is a user error surfaced with
    a message the grid can show next to the cell.
    """

    resolved_unit = normalize_unit(unit)
    value = to_decimal(quantity)
    if value < 0:
        raise ValueError("Operating quantity cannot be negative")
    limit = MAX_HOURS if resolved_unit == UNIT_HOURS else MAX_DAYS
    if value > limit:
        label = "hours (0-24)" if resolved_unit == UNIT_HOURS else "days (0-1)"
        raise ValueError(f"Operating quantity must be entered in {label}")
    return value


# ---------------------------------------------------------------------------
# Money rules
# ---------------------------------------------------------------------------


def service_amount(
    *,
    charging_basis: object,
    charge_category: object,
    quantity: object,
    quantity_unit: object,
    captured_rate: object,
    override_rate: object,
) -> Decimal:
    """Price one daily service line.

    ``captured_rate`` is the unit rate taken from the AFE for this service's
    charging basis (the chosen charge category, the per-service price or the
    per-section amount); ``override_rate`` replaces it when the user typed one.
    """

    basis = normalize_basis(charging_basis)
    rate = effective_rate(captured_rate, override_rate)

    if basis == BASIS_DAILY:
        category = normalize_category(charge_category)
        if category in ONE_TIME_CATEGORIES:
            # One-time cost: charged as a whole amount, never x hours/days.
            return money(rate)
        unit = normalize_unit(quantity_unit)
        quantity_value = validate_quantity(quantity, unit)
        days = days_from_quantity(quantity_value, unit)
        return money(days * rate)

    # Per Service Rate and Per Section Rate are lump sums the AFE allotted.
    return money(rate)


def consumable_amount(
    *,
    category: object,
    quantity: object,
    captured_rate: object,
    override_rate: object,
    manual_amount: object = None,
) -> Decimal:
    """Price one consumable line.

    Cement additives are entered as the total consumption cost for the chosen
    section / phase / sub activity, so a manual amount wins outright. Every
    other category is ``usage x unit rate`` with the override rate taking
    precedence over the captured one.
    """

    resolved = normalize_consumable_category(category)
    if resolved == CEMENT_ADDITIVE and manual_amount is not None and str(manual_amount).strip() != "":
        return money(manual_amount)
    rate = effective_rate(captured_rate, override_rate)
    return money(to_decimal(quantity) * rate)


def tangible_amount(*, quantity: object, captured_rate: object, override_rate: object) -> Decimal:
    """Price one tangible line (``quantity x unit rate``, override wins)."""

    return money(to_decimal(quantity) * effective_rate(captured_rate, override_rate))


# ---------------------------------------------------------------------------
# Lines handed to the engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyServiceLine:
    """One service worked on one day, scoped to section / phase / sub activity."""

    service_id: int
    service_code: str = ""
    service_name: str = ""
    provider_type: str = ""
    charging_basis: str = BASIS_DAILY
    charge_category: str = "Operation"
    section_id: int | None = None
    phase_id: int | None = None
    sub_activity_id: int | None = None
    quantity: Decimal = Decimal("0")
    quantity_unit: str = UNIT_HOURS
    captured_rate: Decimal = Decimal("0")
    override_rate: Decimal | None = None
    remarks: str | None = None
    line_id: int | None = None


@dataclass(frozen=True)
class DailyConsumableLine:
    """One consumed item on one day, scoped to section / phase / sub activity."""

    category: str = MUD_CHEMICAL
    item_id: int | None = None
    item_code: str = ""
    item_name: str = ""
    quantity: Decimal = Decimal("0")
    captured_rate: Decimal = Decimal("0")
    override_rate: Decimal | None = None
    manual_amount: Decimal | None = None
    uom: str | None = None
    currency: str | None = None
    section_id: int | None = None
    phase_id: int | None = None
    sub_activity_id: int | None = None
    remarks: str | None = None
    line_id: int | None = None


@dataclass(frozen=True)
class DailyTangibleLine:
    """One tangible recorded against the day it was consumed/issued."""

    tangible_id: int
    tangible_code: str = ""
    tangible_name: str = ""
    quantity: Decimal = Decimal("1")
    captured_rate: Decimal = Decimal("0")
    override_rate: Decimal | None = None
    uom: str | None = None
    currency: str | None = None
    remarks: str | None = None
    line_id: int | None = None


@dataclass(frozen=True)
class LineResult:
    """A priced line plus the warnings the UI shows next to it."""

    group: str
    code: str
    name: str
    amount: Decimal
    line_id: int | None = None
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# The AFE rate card (read-only snapshot handed to the engine / the page)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SectionRateEntry:
    """A per-section amount configured on an AFE service line."""

    section_id: int
    phase_id: int | None = None
    amount: Decimal = Decimal("0")


@dataclass(frozen=True)
class RateCardEntry:
    """What the AFE says about one service — the source of every unit rate."""

    service_id: int
    service_code: str = ""
    service_name: str = ""
    provider_type: str = ""
    charging_basis: str = BASIS_DAILY
    afe_line_id: int | None = None
    rates: Mapping[str, Decimal] = field(default_factory=dict)
    per_service_amount: Decimal = Decimal("0")
    section_rates: tuple[SectionRateEntry, ...] = ()
    section_id: int | None = None
    phase_id: int | None = None

    def rate_for(self, category: object) -> Decimal:
        """The unit rate of one charge category (0 when not configured)."""

        try:
            key = normalize_category(category)
        except ValueError:
            key = str(category or "")
        return to_decimal(self.rates.get(key))

    def section_amount(self, section_id: int | None, phase_id: int | None = None) -> Decimal:
        """The amount configured for a section (and, when given, that phase)."""

        for entry in self.section_rates:
            if entry.section_id != section_id:
                continue
            if phase_id is not None and entry.phase_id is not None and entry.phase_id != phase_id:
                continue
            return to_decimal(entry.amount)
        return Decimal("0")


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyCostTotals:
    """The day's totals, split by cost group, with every warning collected."""

    services: Decimal = Decimal("0")
    consumables: Decimal = Decimal("0")
    tangibles: Decimal = Decimal("0")
    warnings: tuple[str, ...] = ()

    @property
    def total(self) -> Decimal:
        return money(self.services + self.consumables + self.tangibles)

    @property
    def groups(self) -> tuple[tuple[str, Decimal], ...]:
        return (
            (GROUP_SERVICES, self.services),
            (GROUP_CONSUMABLES, self.consumables),
            (GROUP_TANGIBLES, self.tangibles),
        )


def _price_services(lines: Sequence[DailyServiceLine]) -> tuple[tuple[LineResult, ...], list[str]]:
    results: list[LineResult] = []
    warnings: list[str] = []
    for line in lines:
        try:
            basis = normalize_basis(line.charging_basis)
        except ValueError as exc:
            warnings.append(f"{line.service_code or line.service_id}: {exc}")
            continue
        try:
            amount = service_amount(
                charging_basis=basis,
                charge_category=line.charge_category,
                quantity=line.quantity,
                quantity_unit=line.quantity_unit,
                captured_rate=line.captured_rate,
                override_rate=line.override_rate,
            )
        except ValueError as exc:
            warnings.append(f"{line.service_code or line.service_id}: {exc}")
            amount = Decimal("0")
        line_warnings: list[str] = []
        rate = effective_rate(line.captured_rate, line.override_rate)
        if rate == 0:
            line_warnings.append(
                "no unit rate captured from the AFE and no override rate entered"
            )
        if basis == BASIS_DAILY and is_one_time_category(line.charge_category):
            line_warnings.append(
                f"{normalize_category(line.charge_category)} is a one-time charge — "
                "the entered hours/days are recorded but not multiplied"
            )
        results.append(
            LineResult(
                group=GROUP_SERVICES,
                code=line.service_code,
                name=line.service_name,
                amount=amount,
                line_id=line.line_id,
                warnings=tuple(line_warnings),
            )
        )
        for warning in line_warnings:
            warnings.append(f"{line.service_code or line.service_name or line.service_id}: {warning}")
    return tuple(results), warnings


def _price_consumables(
    lines: Sequence[DailyConsumableLine],
) -> tuple[tuple[LineResult, ...], list[str]]:
    results: list[LineResult] = []
    warnings: list[str] = []
    for line in lines:
        try:
            category = normalize_consumable_category(line.category)
            amount = consumable_amount(
                category=category,
                quantity=line.quantity,
                captured_rate=line.captured_rate,
                override_rate=line.override_rate,
                manual_amount=line.manual_amount,
            )
        except ValueError as exc:
            warnings.append(f"{line.item_code or line.item_name or 'consumable'}: {exc}")
            continue
        if amount == 0:
            note = (
                "no unit rate captured and no override rate entered"
                if category != CEMENT_ADDITIVE
                else "no consumption cost entered"
            )
            warnings.append(f"{line.item_code or line.item_name or category}: {note}")
        results.append(
            LineResult(
                group=GROUP_CONSUMABLES,
                code=line.item_code,
                name=line.item_name,
                amount=amount,
                line_id=line.line_id,
            )
        )
    return tuple(results), warnings


def _price_tangibles(lines: Sequence[DailyTangibleLine]) -> tuple[tuple[LineResult, ...], list[str]]:
    results: list[LineResult] = []
    warnings: list[str] = []
    for line in lines:
        amount = tangible_amount(
            quantity=line.quantity,
            captured_rate=line.captured_rate,
            override_rate=line.override_rate,
        )
        if amount == 0:
            note = "no unit rate captured and no override rate entered"
            warnings.append(f"{line.tangible_code or line.tangible_name}: {note}")
        results.append(
            LineResult(
                group=GROUP_TANGIBLES,
                code=line.tangible_code,
                name=line.tangible_name,
                amount=amount,
                line_id=line.line_id,
            )
        )
    return tuple(results), warnings


@dataclass(frozen=True)
class DailyCostEstimate:
    """Priced lines of one day plus the rollups the report needs."""

    service_lines: tuple[LineResult, ...] = ()
    consumable_lines: tuple[LineResult, ...] = ()
    tangible_lines: tuple[LineResult, ...] = ()
    totals: DailyCostTotals = DailyCostTotals()

    @property
    def total(self) -> Decimal:
        return self.totals.total

    @property
    def results(self) -> tuple[LineResult, ...]:
        return (*self.service_lines, *self.consumable_lines, *self.tangible_lines)

    def amount_of(self, line_id: int | None) -> Decimal:
        """The server-side amount of one line (0 when it is not priced yet)."""

        for result in self.results:
            if result.line_id == line_id:
                return result.amount
        return Decimal("0")


def compile_daily_cost(
    service_lines: Iterable[DailyServiceLine] = (),
    consumable_lines: Iterable[DailyConsumableLine] = (),
    tangible_lines: Iterable[DailyTangibleLine] = (),
) -> DailyCostEstimate:
    """Price every line of one day and roll the amounts up per group."""

    services, service_warnings = _price_services(list(service_lines))
    consumables, consumable_warnings = _price_consumables(list(consumable_lines))
    tangibles, tangible_warnings = _price_tangibles(list(tangible_lines))

    totals = DailyCostTotals(
        services=money(sum((line.amount for line in services), Decimal("0"))),
        consumables=money(sum((line.amount for line in consumables), Decimal("0"))),
        tangibles=money(sum((line.amount for line in tangibles), Decimal("0"))),
        warnings=tuple(dict.fromkeys([*service_warnings, *consumable_warnings, *tangible_warnings])),
    )
    return DailyCostEstimate(
        service_lines=services,
        consumable_lines=consumables,
        tangible_lines=tangibles,
        totals=totals,
    )
