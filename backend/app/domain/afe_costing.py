"""AFE cost estimation engine.

This module is the calculation backbone of the AFE Cost Estimation tab. It is
deliberately framework-free (no FastAPI / SQLAlchemy / Pydantic) so every rule
can be unit-tested with plain dataclasses, and it is deliberately *pure*: given
the same well configuration and the same configured lines it always returns the
same money.

The rules implemented here

1. **Charge categories are constant.** Every service carries the same eight
   charge categories (Mobilization, Demobilization, Operation, Standby,
   Personnel-Operation, Personnel-Standby, Fixed Charge, Others) whether or not
   a rate is configured for them.
2. **Daily Rate** services are charged ``days x unit rate`` for the chosen
   charge category. Quantities may be entered in hours (0-24) or in decimal
   days (``0.2``, ``0.73``); hours are converted with ``/24``. When the user
   has not typed an explicit *Operation* quantity, the planned days of the
   well configuration (for the line's section / phase scope) are used, which is
   the ``planned days x daily rate`` rule.
3. **Mobilization, Demobilization and Fixed Charge are the special case**: they
   are never multiplied by days, sections or services — each is added exactly
   once when a rate exists.
4. **Per Section Rate** services charge the configured amount for that section
   (and, when a phase is given, that phase only).
5. **Per Service Rate** services charge their lump sum once, for the section /
   phase the service was added to.
6. **Consumables and Tangibles** cost ``quantity x effective rate`` where the
   effective rate is the override when one was entered and the rate captured
   from the master data otherwise.
7. Sections and phases always come from the **well configuration**: a line can
   only be scoped to a section / phase that the well actually has.

Rounding: money is quantized to 2 decimals, day quantities to 4 decimals, and
rollups are summed from the already-rounded component amounts so the printed
tables always add up to the printed totals.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

CHARGE_CATEGORIES: tuple[str, ...] = (
    "Mobilization",
    "Demobilization",
    "Operation",
    "Standby",
    "Personnel-Operation",
    "Personnel-Standby",
    "Fixed Charge",
    "Others",
)

#: Charged once per service line, never multiplied by days or sections.
ONE_TIME_CATEGORIES: tuple[str, ...] = ("Mobilization", "Demobilization", "Fixed Charge")

#: Categories that are consumed by a day quantity.
DAY_BASED_CATEGORIES: tuple[str, ...] = (
    "Operation",
    "Standby",
    "Personnel-Operation",
    "Personnel-Standby",
    "Others",
)

BASIS_DAILY = "Daily Rate"
BASIS_PER_SERVICE = "Per Service Rate"
BASIS_PER_SECTION = "Per Section Rate"
CHARGING_BASES: tuple[str, ...] = (BASIS_DAILY, BASIS_PER_SERVICE, BASIS_PER_SECTION)

UNIT_DAYS = "days"
UNIT_HOURS = "hours"
QUANTITY_UNITS: tuple[str, ...] = (UNIT_DAYS, UNIT_HOURS)

AFE_TYPES: tuple[str, ...] = ("Drilling", "Completion")

STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"
AFE_STATUSES: tuple[str, ...] = (STATUS_DRAFT, STATUS_SUBMITTED, STATUS_APPROVED)

GROUP_SERVICES = "Services"
GROUP_CONSUMABLES = "Consumables"
GROUP_TANGIBLES = "Tangibles"

HOURS_PER_DAY = Decimal("24")
MONEY = Decimal("0.01")
DAY_QUANTUM = Decimal("0.0001")


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _fold(value: object) -> str:
    """Fold a label for tolerant comparison (``personnel operation`` matches)."""

    return str(value or "").strip().lower().replace("_", "-").replace(" ", "-")


_CATEGORY_LOOKUP: dict[str, str] = {_fold(name): name for name in CHARGE_CATEGORIES}
_BASIS_LOOKUP: dict[str, str] = {_fold(name): name for name in CHARGING_BASES}
_UNIT_LOOKUP: dict[str, str] = {
    "day": UNIT_DAYS,
    "days": UNIT_DAYS,
    "d": UNIT_DAYS,
    "hour": UNIT_HOURS,
    "hours": UNIT_HOURS,
    "hr": UNIT_HOURS,
    "hrs": UNIT_HOURS,
    "h": UNIT_HOURS,
}


def to_decimal(value: object, default: Decimal = Decimal("0")) -> Decimal:
    """Best-effort Decimal conversion; anything unusable becomes ``default``."""

    if isinstance(value, Decimal):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    try:
        return Decimal(text)
    except ArithmeticError:
        return default


def money(value: object) -> Decimal:
    """Quantize to money (2 decimals, half-up)."""

    return to_decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def normalize_category(value: object) -> str:
    """Map a user/import label onto the canonical charge category."""

    key = _fold(value)
    if key in _CATEGORY_LOOKUP:
        return _CATEGORY_LOOKUP[key]
    raise ValueError(f"Unknown charge category '{value}'")


def normalize_basis(value: object) -> str:
    """Map a user/import label onto the canonical charging basis."""

    key = _fold(value)
    if key in _BASIS_LOOKUP:
        return _BASIS_LOOKUP[key]
    raise ValueError(f"Unknown rate charging criteria '{value}'")


def normalize_unit(value: object, default: str = UNIT_DAYS) -> str:
    """Map a user/import label onto ``days`` or ``hours``."""

    if value is None or str(value).strip() == "":
        return default
    key = _fold(value)
    if key in _UNIT_LOOKUP:
        return _UNIT_LOOKUP[key]
    raise ValueError(f"Quantity unit must be 'days' or 'hours' (got '{value}')")


def days_from_quantity(quantity: object, unit: object = UNIT_DAYS) -> Decimal:
    """Convert an entered quantity into days.

    Hours are divided by 24 so ``12 hours`` and ``0.5 days`` cost the same.
    """

    resolved_unit = normalize_unit(unit)
    days = to_decimal(quantity)
    if days < 0:
        raise ValueError("Quantity cannot be negative")
    if resolved_unit == UNIT_HOURS:
        days = days / HOURS_PER_DAY
    return days.quantize(DAY_QUANTUM, rounding=ROUND_HALF_UP)


def effective_rate(captured: object, override: object) -> Decimal:
    """The rate to charge: the override when present, else the captured rate."""

    if override is None or str(override).strip() == "":
        return to_decimal(captured)
    return to_decimal(override)


def scope_label(code: object, name: object) -> str:
    """``SEC1 — Surface`` style label that degrades gracefully."""

    text_code = str(code or "").strip()
    text_name = str(name or "").strip()
    if text_code and text_name:
        return f"{text_code} — {text_name}"
    return text_code or text_name or "—"


# ---------------------------------------------------------------------------
# Well configuration (read-only snapshot handed to the engine)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WellPhaseScope:
    """One phase of one configured section, with its planned days."""

    phase_id: int
    phase_code: str | None = None
    phase_name: str | None = None
    days: Decimal = Decimal("0")

    @property
    def label(self) -> str:
        return scope_label(self.phase_code, self.phase_name)


@dataclass(frozen=True)
class WellSectionScope:
    """One configured hole section with from/to depth and its phases."""

    section_id: int
    section_code: str | None = None
    section_name: str | None = None
    from_depth: Decimal = Decimal("0")
    to_depth: Decimal = Decimal("0")
    phases: tuple[WellPhaseScope, ...] = ()

    @property
    def label(self) -> str:
        return scope_label(self.section_code, self.section_name)

    @property
    def total_days(self) -> Decimal:
        return sum((phase.days for phase in self.phases), Decimal("0"))


@dataclass(frozen=True)
class WellScope:
    """The well configuration an AFE is estimated against."""

    well_code: str = ""
    well_name: str = ""
    depth_unit: str = "m"
    sections: tuple[WellSectionScope, ...] = ()

    @property
    def total_days(self) -> Decimal:
        return sum((section.total_days for section in self.sections), Decimal("0"))

    @property
    def total_depth(self) -> Decimal | None:
        return self.sections[-1].to_depth if self.sections else None

    def find_section(self, section_id: int | None) -> WellSectionScope | None:
        if section_id is None:
            return None
        for section in self.sections:
            if section.section_id == section_id:
                return section
        return None

    def has_phase(self, section_id: int | None, phase_id: int | None) -> bool:
        """True when the well configuration really contains that phase."""

        if phase_id is None:
            return False
        candidates = (
            [self.find_section(section_id)] if section_id is not None else list(self.sections)
        )
        return any(
            phase.phase_id == phase_id
            for section in candidates
            if section is not None
            for phase in section.phases
        )

    def phase_code_and_name(self, phase_id: int | None) -> tuple[str | None, str | None]:
        if phase_id is None:
            return (None, None)
        for section in self.sections:
            for phase in section.phases:
                if phase.phase_id == phase_id:
                    return (phase.phase_code, phase.phase_name)
        return (None, None)

    def planned_days(self, section_id: int | None = None, phase_id: int | None = None) -> Decimal:
        """Planned days inside a scope: whole well, one section or one phase."""

        total = Decimal("0")
        for section in self.sections:
            if section_id is not None and section.section_id != section_id:
                continue
            for phase in section.phases:
                if phase_id is not None and phase.phase_id != phase_id:
                    continue
                total += phase.days
        return total


# ---------------------------------------------------------------------------
# Configured estimate lines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChargeLine:
    """A day-based quantity entered against one charge category."""

    category: str
    quantity: Decimal
    unit: str = UNIT_DAYS


@dataclass(frozen=True)
class SectionRate:
    """Per-section charge: a constant amount for one section (optionally a phase)."""

    section_id: int
    phase_id: int | None = None
    amount: Decimal = Decimal("0")


@dataclass(frozen=True)
class ServiceLine:
    """One service added to an AFE with its charging basis and rate card."""

    service_id: int
    service_code: str = ""
    service_name: str = ""
    provider_type: str = ""
    charging_basis: str = BASIS_DAILY
    #: Canonical charge category → unit rate. Missing categories mean "not charged".
    rates: Mapping[str, Decimal] = field(default_factory=dict)
    charge_lines: Sequence[ChargeLine] = ()
    section_rates: Sequence[SectionRate] = ()
    per_service_amount: Decimal = Decimal("0")
    section_id: int | None = None
    phase_id: int | None = None
    effective_date: object = None
    remarks: str | None = None
    line_id: int | None = None

    def rate_for(self, category: str) -> Decimal:
        return to_decimal(self.rates.get(category))


@dataclass(frozen=True)
class ConsumableLine:
    """One consumable item, scoped to a section and/or a phase of the well."""

    item_id: int
    item_code: str = ""
    item_name: str = ""
    item_kind: str = "mud_chemical"
    quantity: Decimal = Decimal("1")
    captured_rate: Decimal = Decimal("0")
    override_rate: Decimal | None = None
    uom: str | None = None
    currency: str | None = None
    section_id: int | None = None
    phase_id: int | None = None
    remarks: str | None = None
    line_id: int | None = None


@dataclass(frozen=True)
class TangibleLine:
    """One tangible item for the well, with an optional override rate."""

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


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CostComponent:
    """One priced row of the breakdown — the smallest unit of AFE money."""

    group: str
    category: str
    description: str
    amount: Decimal
    quantity: Decimal | None = None
    rate: Decimal | None = None
    unit: str | None = None
    section_id: int | None = None
    section_label: str | None = None
    phase_id: int | None = None
    phase_label: str | None = None


@dataclass(frozen=True)
class LineEstimate:
    """Estimated cost of one configured line, with its breakdown."""

    group: str
    code: str
    name: str
    amount: Decimal
    basis: str | None = None
    components: tuple[CostComponent, ...] = ()
    warnings: tuple[str, ...] = ()
    line_id: int | None = None
    section_id: int | None = None
    section_label: str | None = None
    phase_id: int | None = None
    phase_label: str | None = None


@dataclass(frozen=True)
class GroupEstimate:
    """One of the three cost groups: Services, Consumables or Tangibles."""

    group: str
    amount: Decimal
    lines: tuple[LineEstimate, ...] = ()

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass(frozen=True)
class SectionRollup:
    """Cost attributed to one configured section (``None`` = well-wide)."""

    section_id: int | None
    section_label: str
    planned_days: Decimal
    amount: Decimal


@dataclass(frozen=True)
class AfeEstimate:
    """The compiled AFE cost estimate."""

    services: GroupEstimate
    consumables: GroupEstimate
    tangibles: GroupEstimate
    by_section: tuple[SectionRollup, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def total(self) -> Decimal:
        return money(self.services.amount + self.consumables.amount + self.tangibles.amount)

    @property
    def groups(self) -> tuple[GroupEstimate, ...]:
        return (self.services, self.consumables, self.tangibles)

    @property
    def components(self) -> tuple[CostComponent, ...]:
        return tuple(
            component
            for group in self.groups
            for line in group.lines
            for component in line.components
        )


# ---------------------------------------------------------------------------
# Scope resolution
# ---------------------------------------------------------------------------


def resolve_scope(
    well: WellScope, section_id: int | None, phase_id: int | None
) -> tuple[str | None, str | None, tuple[str, ...]]:
    """Resolve a scope to display labels and collect scope warnings."""

    warnings: list[str] = []
    section_text: str | None = None
    phase_text: str | None = None
    if section_id is not None:
        section = well.find_section(section_id)
        if section is None:
            warnings.append("scoped section is not part of the well configuration")
        else:
            section_text = section.label
    if phase_id is not None:
        if not well.has_phase(section_id, phase_id):
            warnings.append("scoped phase is not part of the well configuration")
        else:
            code, name = well.phase_code_and_name(phase_id)
            phase_text = scope_label(code, name)
    return section_text, phase_text, tuple(warnings)


# ---------------------------------------------------------------------------
# Service estimation
# ---------------------------------------------------------------------------


def _one_time_components(
    line: ServiceLine, section_text: str | None, phase_text: str | None
) -> list[CostComponent]:
    """Mobilization / Demobilization / Fixed Charge — added exactly once each."""

    components: list[CostComponent] = []
    for category in ONE_TIME_CATEGORIES:
        rate = line.rate_for(category)
        if rate == 0:
            continue
        components.append(
            CostComponent(
                group=GROUP_SERVICES,
                category=category,
                description=f"{category} — charged once",
                quantity=Decimal("1"),
                rate=money(rate),
                amount=money(rate),
                section_id=line.section_id,
                section_label=section_text,
                phase_id=line.phase_id,
                phase_label=phase_text,
            )
        )
    return components


def estimate_service_line(line: ServiceLine, well: WellScope) -> LineEstimate:
    """Estimate one service line against the well configuration."""

    basis = normalize_basis(line.charging_basis)
    section_text, phase_text, scope_warnings = resolve_scope(well, line.section_id, line.phase_id)
    warnings: list[str] = list(scope_warnings)
    components: list[CostComponent] = []

    def add(
        category: str,
        description: str,
        amount: Decimal,
        *,
        quantity: Decimal | None = None,
        rate: Decimal | None = None,
        unit: str | None = None,
        section_id: int | None = line.section_id,
        section_label: str | None = section_text,
        phase_id: int | None = line.phase_id,
        phase_label: str | None = phase_text,
    ) -> None:
        components.append(
            CostComponent(
                group=GROUP_SERVICES,
                category=category,
                description=description,
                quantity=quantity,
                rate=money(rate) if rate is not None else None,
                unit=unit,
                amount=money(amount),
                section_id=section_id,
                section_label=section_label,
                phase_id=phase_id,
                phase_label=phase_label,
            )
        )

    if basis == BASIS_DAILY:
        operation_days_entered = Decimal("0")
        
        # We will collect daily charges and then optionally split them if well-wide
        daily_charges = []
        
        for charge in line.charge_lines:
            category = normalize_category(charge.category)
            days = days_from_quantity(charge.quantity, charge.unit)
            rate = line.rate_for(category)
            if category == "Operation":
                operation_days_entered += days
            if rate == 0 and days != 0:
                warnings.append(f"{category}: no unit rate configured")
            daily_charges.append({
                "category": category,
                "days": days,
                "rate": rate,
                "is_explicit": True
            })

        # The well configuration drives the Operation days unless the user has
        # typed an explicit Operation quantity for this line.
        if operation_days_entered == 0:
            operation_rate = line.rate_for("Operation")
            if operation_rate != 0:
                planned = well.planned_days(line.section_id, line.phase_id)
                if planned == 0:
                    warnings.append(
                        "Operation rate set but the well configuration has no planned days"
                    )
                else:
                    daily_charges.append({
                        "category": "Operation",
                        "days": planned,
                        "rate": operation_rate,
                        "is_explicit": False
                    })
                    
        # Now output the charges, splitting by section if line.section_id is None
        for charge in daily_charges:
            cat = charge["category"]
            days = charge["days"]
            rate = charge["rate"]
            
            if days == 0:
                continue

            if line.section_id is None and well.total_days > 0:
                # Split well-wide daily charges across sections based on planned days
                for section in well.sections:
                    sec_days = section.total_days
                    if sec_days == 0:
                        continue
                        
                    if charge["is_explicit"]:
                        # Proportion of explicit days
                        split_days = days * (sec_days / well.total_days)
                    else:
                        # Implicit operation days directly from section
                        split_days = sec_days
                        
                    add(
                        cat,
                        f"{cat} — {split_days.normalize()} day(s) @ {money(rate)}",
                        split_days * rate,
                        quantity=split_days,
                        rate=rate,
                        unit=UNIT_DAYS,
                        section_id=section.section_id,
                        section_label=section.label,
                        phase_id=None,
                        phase_label=None,
                    )
            else:
                add(
                    cat,
                    f"{cat} — {days.normalize()} day(s) @ {money(rate)}",
                    days * rate,
                    quantity=days,
                    rate=rate,
                    unit=UNIT_DAYS,
                )

    elif basis == BASIS_PER_SECTION:
        if not line.section_rates:
            warnings.append("per section rate selected but no section rate entered")
        for entry in line.section_rates:
            section = well.find_section(entry.section_id)
            if section is None:
                warnings.append("a section rate refers to a section outside the well configuration")
                continue
            entry_phase_text: str | None = None
            if entry.phase_id is not None:
                if not well.has_phase(entry.section_id, entry.phase_id):
                    warnings.append(
                        f"{section.label}: phase rate refers to a phase outside the well"
                    )
                    continue
                code, name = well.phase_code_and_name(entry.phase_id)
                entry_phase_text = scope_label(code, name)
            add(
                "Per Section Rate",
                f"{section.label}"
                + (f" / {entry_phase_text}" if entry_phase_text else "")
                + " — constant rate",
                entry.amount,
                quantity=Decimal("1"),
                rate=entry.amount,
                section_id=entry.section_id,
                section_label=section.label,
                phase_id=entry.phase_id,
                phase_label=entry_phase_text,
            )
    else:  # BASIS_PER_SERVICE
        amount = to_decimal(line.per_service_amount)
        if amount == 0:
            warnings.append("per service rate selected but no service price entered")
        scope = " · ".join(text for text in (section_text, phase_text) if text) or "whole well"
        add(
            "Per Service Rate",
            f"Per service price — {scope}",
            amount,
            quantity=Decimal("1"),
            rate=amount,
        )

    components.extend(_one_time_components(line, section_text, phase_text))
    total = sum((component.amount for component in components), Decimal("0"))
    return LineEstimate(
        group=GROUP_SERVICES,
        code=line.service_code,
        name=line.service_name,
        amount=money(total),
        basis=basis,
        components=tuple(components),
        warnings=tuple(dict.fromkeys(warnings)),
        line_id=line.line_id,
        section_id=line.section_id,
        section_label=section_text,
        phase_id=line.phase_id,
        phase_label=phase_text,
    )


# ---------------------------------------------------------------------------
# Consumable / tangible estimation
# ---------------------------------------------------------------------------


def estimate_consumable_line(line: ConsumableLine, well: WellScope) -> LineEstimate:
    """Consumables cost ``quantity x effective rate``; the scope is reported."""

    section_text, phase_text, warnings = resolve_scope(well, line.section_id, line.phase_id)
    warning_list = list(warnings)
    if line.section_id is None and line.phase_id is None:
        warning_list.append("not scoped to a section or phase")
    quantity = to_decimal(line.quantity)
    rate = effective_rate(line.captured_rate, line.override_rate)
    amount = money(quantity * rate)
    scope = " · ".join(text for text in (section_text, phase_text) if text) or "whole well"
    component = CostComponent(
        group=GROUP_CONSUMABLES,
        category="Consumption",
        description=f"{line.item_name} — {quantity} {line.uom or 'unit'} @ {money(rate)} · {scope}",
        quantity=quantity,
        rate=money(rate),
        unit=line.uom,
        amount=amount,
        section_id=line.section_id,
        section_label=section_text,
        phase_id=line.phase_id,
        phase_label=phase_text,
    )
    return LineEstimate(
        group=GROUP_CONSUMABLES,
        code=line.item_code,
        name=line.item_name,
        amount=amount,
        components=(component,),
        warnings=tuple(warning_list),
        line_id=line.line_id,
        section_id=line.section_id,
        section_label=section_text,
        phase_id=line.phase_id,
        phase_label=phase_text,
    )


def estimate_tangible_line(line: TangibleLine) -> LineEstimate:
    """Tangibles cost ``quantity x effective rate`` (override wins)."""

    quantity = to_decimal(line.quantity)
    rate = effective_rate(line.captured_rate, line.override_rate)
    overridden = line.override_rate is not None and str(line.override_rate).strip() != ""
    amount = money(quantity * rate)
    component = CostComponent(
        group=GROUP_TANGIBLES,
        category="Override rate" if overridden else "Captured rate",
        description=f"{line.tangible_name} — {quantity} {line.uom or 'unit'} @ {money(rate)}",
        quantity=quantity,
        rate=money(rate),
        unit=line.uom,
        amount=amount,
    )
    warnings: list[str] = []
    if rate == 0:
        warnings.append("no rate captured and no override rate entered")
    return LineEstimate(
        group=GROUP_TANGIBLES,
        code=line.tangible_code,
        name=line.tangible_name,
        amount=amount,
        components=(component,),
        warnings=tuple(warnings),
        line_id=line.line_id,
    )


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


def _group_total(lines: Sequence[LineEstimate]) -> Decimal:
    return money(sum((line.amount for line in lines), Decimal("0")))


def section_rollup(
    well: WellScope,
    services: Sequence[LineEstimate],
    consumables: Sequence[LineEstimate],
    tangibles: Sequence[LineEstimate],
) -> tuple[SectionRollup, ...]:
    """Attribute every component to a configured section (or well-wide)."""

    buckets: dict[int | None, Decimal] = {section.section_id: Decimal("0") for section in well.sections}
    buckets[None] = Decimal("0")
    for group in (services, consumables, tangibles):
        for line in group:
            for component in line.components:
                key = component.section_id if component.section_id in buckets else None
                buckets[key] = buckets[key] + component.amount

    rollup: list[SectionRollup] = [
        SectionRollup(
            section_id=section.section_id,
            section_label=section.label,
            planned_days=section.total_days,
            amount=money(buckets.get(section.section_id, Decimal("0"))),
        )
        for section in well.sections
    ]
    if buckets[None] != 0:
        rollup.append(
            SectionRollup(
                section_id=None,
                section_label="Well-wide (no section)",
                planned_days=Decimal("0"),
                amount=money(buckets[None]),
            )
        )
    return tuple(rollup)


def compile_afe_estimate(
    well: WellScope,
    service_lines: Sequence[ServiceLine] = (),
    consumable_lines: Sequence[ConsumableLine] = (),
    tangible_lines: Sequence[TangibleLine] = (),
) -> AfeEstimate:
    """Compile the three cost groups into the final AFE cost estimate."""

    services = tuple(estimate_service_line(line, well) for line in service_lines)
    consumables = tuple(estimate_consumable_line(line, well) for line in consumable_lines)
    tangibles = tuple(estimate_tangible_line(line) for line in tangible_lines)

    warnings: list[str] = []
    if not well.sections:
        warnings.append(
            "The well has no configuration yet — configure its sections and phases in "
            "Rig & Well Management to drive the day-based estimates."
        )
    for group in (services, consumables, tangibles):
        for line in group:
            for warning in line.warnings:
                warnings.append(f"{line.code or line.name}: {warning}")

    return AfeEstimate(
        services=GroupEstimate(GROUP_SERVICES, _group_total(services), services),
        consumables=GroupEstimate(GROUP_CONSUMABLES, _group_total(consumables), consumables),
        tangibles=GroupEstimate(GROUP_TANGIBLES, _group_total(tangibles), tangibles),
        by_section=section_rollup(well, services, consumables, tangibles),
        warnings=tuple(dict.fromkeys(warnings)),
    )
