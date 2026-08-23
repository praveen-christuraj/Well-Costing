"""The registry of data sources a dropdown may be bound to.

A *source* is one readable list of options. Three kinds exist:

``master_data``
    A row set from the master-data registry (``ENTITY_CONFIGS``), e.g.
    ``secondary-categories`` or ``units``.
``catalog``
    Catalogue items narrowed to one ``item_type`` (or all of them), e.g. only
    tangibles. Catalogue sources additionally understand classification
    filters, which is what makes Primary → Secondary → Tertiary cascading work.
``procurement``
    Service orders and purchase orders. These are *reference registers*: an
    order is looked up for traceability and is never required to point at a
    service or an item.
``static``
    A fixed, code-owned enumeration such as rate bases. Listed so a slot can
    declare a static default rather than pretending to be configurable.

Sources are declared here, once, so the super-admin console can only ever bind
a dropdown to something the backend can actually resolve.
"""

from dataclasses import dataclass, field

#: Label formats a binding may choose between. Anything else is rejected.
LABEL_TEMPLATES: tuple[str, ...] = (
    "{code} — {name}",
    "{name}",
    "{code}",
    "{name} ({code})",
)

DEFAULT_LABEL_TEMPLATE = LABEL_TEMPLATES[0]


@dataclass(frozen=True)
class ReferenceSource:
    """One resolvable list of dropdown options."""

    code: str
    label: str
    kind: str
    #: Master-data entity key, catalogue ``item_type``, or ``None`` for "all".
    entity: str | None = None
    description: str = ""
    #: Column on the source that points at its parent, enabling cascades.
    parent_field: str | None = None
    #: Source code of the parent list, when this source cascades from another.
    parent_source: str | None = None
    #: Filter columns a binding may pin to a fixed value.
    filterable: tuple[str, ...] = field(default_factory=tuple)
    #: Static options, only for ``kind == "static"``.
    options: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def is_cascading(self) -> bool:
        return self.parent_field is not None


_CLASSIFICATION_FILTERS = (
    "primary_category_id",
    "secondary_category_id",
    "tertiary_category_id",
)

_CATALOG_FILTERS = (*_CLASSIFICATION_FILTERS, "cost_category_id", "cost_code_id", "default_unit_id")


def _catalog_source(
    code: str, label: str, item_type: str | None, description: str
) -> ReferenceSource:
    return ReferenceSource(
        code=code,
        label=label,
        kind="catalog",
        entity=item_type,
        description=description,
        parent_field="secondary_category_id",
        parent_source="classification.secondary",
        filterable=_CATALOG_FILTERS,
    )


SOURCES: tuple[ReferenceSource, ...] = (
    # -- classification ---------------------------------------------------
    ReferenceSource(
        code="classification.primary",
        label="Primary Categories",
        kind="master_data",
        entity="primary-categories",
        description="Top level of the single classification hierarchy.",
    ),
    ReferenceSource(
        code="classification.secondary",
        label="Secondary Categories",
        kind="master_data",
        entity="secondary-categories",
        description="Second level; cascades from a primary category.",
        parent_field="primary_category_id",
        parent_source="classification.primary",
        filterable=("primary_category_id",),
    ),
    ReferenceSource(
        code="classification.tertiary",
        label="Tertiary Categories",
        kind="master_data",
        entity="tertiary-categories",
        description="Third level; cascades from a secondary category.",
        parent_field="secondary_category_id",
        parent_source="classification.secondary",
        filterable=("secondary_category_id",),
    ),
    # -- configuration ----------------------------------------------------
    ReferenceSource(
        code="master.units",
        label="Units of Measure",
        kind="master_data",
        entity="units",
        description="Units of measure register.",
    ),
    ReferenceSource(
        code="master.currencies",
        label="Currencies",
        kind="master_data",
        entity="currencies",
        description="Currency register.",
    ),
    ReferenceSource(
        code="master.hole-sections",
        label="Hole Sections",
        kind="master_data",
        entity="hole-sections",
        description="Configurable drilling hole sections.",
    ),
    ReferenceSource(
        code="master.phases",
        label="Phases",
        kind="master_data",
        entity="phases",
        description="Operational phases, maintained once in master data.",
    ),
    ReferenceSource(
        code="master.activities",
        label="Activities",
        kind="master_data",
        entity="activities",
        description="Master activities — Planned, NPT, UPA.",
    ),
    ReferenceSource(
        code="master.vendors",
        label="Vendors",
        kind="master_data",
        entity="vendors",
        description="Vendor register.",
        filterable=("vendor_type",),
    ),
    # -- costing ----------------------------------------------------------
    ReferenceSource(
        code="costing.cost-categories",
        label="Cost Categories",
        kind="master_data",
        entity="cost-categories",
        description="Cost categories, themselves classified by primary/secondary.",
        filterable=("primary_category_id", "secondary_category_id"),
    ),
    ReferenceSource(
        code="costing.cost-codes",
        label="Cost Codes",
        kind="master_data",
        entity="cost-codes",
        description="Cost codes; cascades from a cost category.",
        parent_field="cost_category_id",
        parent_source="costing.cost-categories",
        filterable=("cost_category_id",),
    ),
    # -- catalogue --------------------------------------------------------
    _catalog_source(
        "catalog.all", "Catalogue — all items", None, "Every catalogue item regardless of type."
    ),
    _catalog_source("catalog.services", "Catalogue — services", "service", "Service items."),
    _catalog_source("catalog.tangibles", "Catalogue — tangibles", "tangible", "Tangible items."),
    _catalog_source(
        "catalog.mud-chemicals", "Catalogue — mud chemicals", "mud_chemical", "Mud chemicals."
    ),
    _catalog_source(
        "catalog.cement-additives",
        "Catalogue — cement additives",
        "cement_additive",
        "Cement additives.",
    ),
    _catalog_source("catalog.materials", "Catalogue — materials", "material", "Materials."),
    _catalog_source("catalog.equipment", "Catalogue — equipment", "equipment", "Equipment."),
    ReferenceSource(
        code="catalog.consumables",
        label="Catalogue — consumables",
        kind="catalog",
        entity="mud_chemical,cement_additive",
        description="Mud chemicals and cement additives together.",
        parent_field="secondary_category_id",
        parent_source="classification.secondary",
        filterable=_CATALOG_FILTERS,
    ),
    # -- procurement (reference registers) --------------------------------
    ReferenceSource(
        code="procurement.service-orders",
        label="Service Orders (reference)",
        kind="procurement",
        entity="service-orders",
        description=(
            "Service orders held purely for reference and traceability — never "
            "required to be linked to a service."
        ),
        filterable=("vendor_id", "status"),
    ),
    ReferenceSource(
        code="procurement.purchase-orders",
        label="Purchase Orders (reference)",
        kind="procurement",
        entity="purchase-orders",
        description=(
            "Purchase orders held purely for reference and traceability — never "
            "required to be linked to a catalogue item."
        ),
        filterable=("vendor_id", "status"),
    ),
    # -- static -----------------------------------------------------------
    ReferenceSource(
        code="static.rate-bases",
        label="Rate bases",
        kind="static",
        description="Code-owned pricing bases.",
        options=(
            ("daily", "Daily"),
            ("per_section", "Per hole section"),
            ("per_service", "Per service"),
            ("fixed", "Fixed"),
            ("per_unit", "Per unit"),
            ("daily_consumption", "Daily consumption"),
        ),
    ),
    ReferenceSource(
        code="static.vendor-types",
        label="Vendor types",
        kind="static",
        description="Third party or in-house.",
        options=(("third_party", "Third party"), ("inhouse", "In-house")),
    ),
    #: Well-scoped sub-activities are resolved against the well being edited and
    #: therefore cannot be rebound to anything else.
    ReferenceSource(
        code="well.sub-activities",
        label="Well sub-activities",
        kind="well_scoped",
        entity="well-activities",
        description=(
            "Sub-activities configured per well while entering daily cost data; "
            "always scoped to the selected well."
        ),
        parent_field="well_id",
        filterable=("well_id", "activity_id"),
    ),
)

SOURCES_BY_CODE: dict[str, ReferenceSource] = {source.code: source for source in SOURCES}


def get_source(code: str) -> ReferenceSource:
    """Return the registered source, or raise ``KeyError`` when unknown."""

    return SOURCES_BY_CODE[code]
