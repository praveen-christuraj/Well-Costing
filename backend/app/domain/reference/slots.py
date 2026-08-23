"""The registry of dropdown slots the application renders.

A *slot* is a stable name for one picker in the UI. Screens ask for options by
slot code and never by table name, so where a dropdown gets its data is a
configuration decision instead of a code change.

Two properties keep this safe as the application grows:

``allowed_sources``
    A slot can only be pointed at sources that make sense for it. The AFE line
    classification pickers, for example, can only ever read the classification
    hierarchy.
``locked``
    Structural slots (well-scoped sub-activities, the classification cascade
    itself) cannot be rebound at all. They are listed for visibility so the
    console shows the complete picture rather than a partial one.
"""

from dataclasses import dataclass, field

from app.domain.reference.sources import SOURCES_BY_CODE

MODULES: tuple[tuple[str, str], ...] = (
    ("master-data", "Master Data"),
    ("afe", "AFE"),
    ("cost-builder", "Cost Builder"),
    ("daily-cost", "Daily Cost"),
    ("procurement", "Procurement & Rates"),
)


@dataclass(frozen=True)
class DropdownSlot:
    """One named picker in the UI and the sources it may read."""

    code: str
    module: str
    label: str
    description: str
    default_source: str
    allowed_sources: tuple[str, ...] = field(default_factory=tuple)
    #: Slot code this one cascades from, if any (parent selection filters it).
    cascades_from: str | None = None
    #: Structural slots cannot be rebound by an administrator.
    locked: bool = False
    #: Filters always applied, on top of anything the binding adds.
    fixed_filters: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def selectable_sources(self) -> tuple[str, ...]:
        if self.locked:
            return (self.default_source,)
        return self.allowed_sources or (self.default_source,)


_CLASSIFICATION = ("classification.primary", "classification.secondary", "classification.tertiary")
_CATALOG_SOURCES = tuple(code for code in SOURCES_BY_CODE if code.startswith("catalog."))


def _classification_trio(
    module: str, prefix: str, subject: str, *, locked: bool = True
) -> tuple[DropdownSlot, ...]:
    """The Primary → Secondary → Tertiary cascade for one screen."""

    return (
        DropdownSlot(
            code=f"{prefix}.primary_category",
            module=module,
            label=f"{subject} — Primary Category",
            description=f"Primary classification of the {subject.lower()}.",
            default_source="classification.primary",
            allowed_sources=_CLASSIFICATION,
            locked=locked,
        ),
        DropdownSlot(
            code=f"{prefix}.secondary_category",
            module=module,
            label=f"{subject} — Secondary Category",
            description=(
                f"Secondary classification of the {subject.lower()}; "
                "cascades from the primary category."
            ),
            default_source="classification.secondary",
            allowed_sources=_CLASSIFICATION,
            cascades_from=f"{prefix}.primary_category",
            locked=locked,
        ),
        DropdownSlot(
            code=f"{prefix}.tertiary_category",
            module=module,
            label=f"{subject} — Tertiary Category",
            description=(
                f"Third-level classification of the {subject.lower()}; "
                "cascades from the secondary category."
            ),
            default_source="classification.tertiary",
            allowed_sources=_CLASSIFICATION,
            cascades_from=f"{prefix}.secondary_category",
            locked=locked,
        ),
    )


SLOTS: tuple[DropdownSlot, ...] = (
    # ---------------------------------------------------------------- master data
    *_classification_trio("master-data", "catalogue.item", "Catalogue item"),
    DropdownSlot(
        code="catalogue.item.unit",
        module="master-data",
        label="Catalogue item — Unit of measure",
        description="Default unit offered on catalogue items.",
        default_source="master.units",
        allowed_sources=("master.units",),
    ),
    DropdownSlot(
        code="cost_category.primary_category",
        module="master-data",
        label="Cost category — Parent (Primary Category)",
        description="The parent of a cost category, taken from the classification.",
        default_source="classification.primary",
        allowed_sources=_CLASSIFICATION,
    ),
    DropdownSlot(
        code="cost_category.secondary_category",
        module="master-data",
        label="Cost category — Secondary Category",
        description="Second level of a cost category; cascades from its parent.",
        default_source="classification.secondary",
        allowed_sources=_CLASSIFICATION,
        cascades_from="cost_category.primary_category",
    ),
    DropdownSlot(
        code="cost_code.cost_category",
        module="master-data",
        label="Cost code — Cost Category",
        description="The cost category a cost code belongs to.",
        default_source="costing.cost-categories",
        allowed_sources=("costing.cost-categories",),
    ),
    # ------------------------------------------------------------------------ AFE
    DropdownSlot(
        code="afe.section.phase",
        module="afe",
        label="AFE section — Phase",
        description=(
            "Operational phase for an AFE section, read straight from master data. "
            "Phases are not configured inside the AFE."
        ),
        default_source="master.phases",
        allowed_sources=("master.phases",),
    ),
    DropdownSlot(
        code="afe.section.hole_section",
        module="afe",
        label="AFE section — Hole section",
        description="Hole section for an AFE section row.",
        default_source="master.hole-sections",
        allowed_sources=("master.hole-sections",),
    ),
    *_classification_trio("afe", "afe.line", "AFE line"),
    DropdownSlot(
        code="afe.line.item",
        module="afe",
        label="AFE line — Item",
        description=(
            "Catalogue item for an AFE line. Always narrowed by the line's "
            "classification, so an AFE line can only ever be built from the "
            "classification hierarchy."
        ),
        default_source="catalog.all",
        allowed_sources=_CATALOG_SOURCES,
        cascades_from="afe.line.secondary_category",
    ),
    DropdownSlot(
        code="afe.line.cost_code",
        module="afe",
        label="AFE line — Cost code",
        description="Cost code charged by the line.",
        default_source="costing.cost-codes",
        allowed_sources=("costing.cost-codes",),
    ),
    DropdownSlot(
        code="afe.line.unit",
        module="afe",
        label="AFE line — Unit",
        description="Unit of measure for the planned quantity.",
        default_source="master.units",
        allowed_sources=("master.units",),
    ),
    # ----------------------------------------------------------------- daily cost
    DropdownSlot(
        code="daily_cost.phase",
        module="daily-cost",
        label="Daily cost — Phase",
        description="Operational phase of the day, read from master data.",
        default_source="master.phases",
        allowed_sources=("master.phases",),
    ),
    DropdownSlot(
        code="daily_cost.hole_section",
        module="daily-cost",
        label="Daily cost — Hole section",
        description="Hole section being drilled.",
        default_source="master.hole-sections",
        allowed_sources=("master.hole-sections",),
    ),
    DropdownSlot(
        code="daily_cost.activity",
        module="daily-cost",
        label="Daily cost — Activity",
        description="Master activity (Planned, NPT, UPA) the sub-activity rolls up to.",
        default_source="master.activities",
        allowed_sources=("master.activities",),
    ),
    DropdownSlot(
        code="daily_cost.sub_activity",
        module="daily-cost",
        label="Daily cost — Sub-activity",
        description=(
            "Well-scoped sub-activity, configured while entering daily cost data. "
            "Always resolved against the selected well."
        ),
        default_source="well.sub-activities",
        locked=True,
        cascades_from="daily_cost.activity",
    ),
    DropdownSlot(
        code="daily_cost.service_item",
        module="daily-cost",
        label="Daily cost — Service item",
        description="Catalogue item used on a daily service line.",
        default_source="catalog.services",
        allowed_sources=_CATALOG_SOURCES,
    ),
    DropdownSlot(
        code="daily_cost.consumable_item",
        module="daily-cost",
        label="Daily cost — Consumable item",
        description="Catalogue item used on a daily consumable line.",
        default_source="catalog.consumables",
        allowed_sources=_CATALOG_SOURCES,
    ),
    DropdownSlot(
        code="daily_cost.vendor",
        module="daily-cost",
        label="Daily cost — Vendor",
        description="Vendor supplying the line.",
        default_source="master.vendors",
        allowed_sources=("master.vendors",),
    ),
    # -------------------------------------------------------- procurement & rates
    DropdownSlot(
        code="rates.item",
        module="procurement",
        label="Tangible rate — Item",
        description="Catalogue item a master rate is recorded against.",
        default_source="catalog.tangibles",
        allowed_sources=_CATALOG_SOURCES,
    ),
    DropdownSlot(
        code="rates.purchase_order",
        module="procurement",
        label="Tangible rate — Purchase order",
        description=(
            "Optional purchase-order reference on a rate. Reference only — a rate "
            "never has to be linked to an order."
        ),
        default_source="procurement.purchase-orders",
        allowed_sources=("procurement.purchase-orders", "procurement.service-orders"),
    ),
    DropdownSlot(
        code="rates.vendor",
        module="procurement",
        label="Tangible rate — Vendor",
        description="Vendor quoting the rate.",
        default_source="master.vendors",
        allowed_sources=("master.vendors",),
    ),
    DropdownSlot(
        code="rates.currency",
        module="procurement",
        label="Tangible rate — Currency",
        description="Currency of the rate.",
        default_source="master.currencies",
        allowed_sources=("master.currencies",),
    ),
    DropdownSlot(
        code="rates.unit",
        module="procurement",
        label="Tangible rate — Unit",
        description="Unit the rate is quoted per.",
        default_source="master.units",
        allowed_sources=("master.units",),
    ),
)

SLOTS_BY_CODE: dict[str, DropdownSlot] = {slot.code: slot for slot in SLOTS}


def get_slot(code: str) -> DropdownSlot:
    """Return the registered slot, or raise ``KeyError`` when unknown."""

    return SLOTS_BY_CODE[code]


def slots_for_module(module: str) -> tuple[DropdownSlot, ...]:
    return tuple(slot for slot in SLOTS if slot.module == module)
