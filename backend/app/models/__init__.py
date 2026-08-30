"""SQLAlchemy model exports used by Alembic metadata discovery."""

# pyright: reportAttributeAccessIssue=false, reportUnknownVariableType=false

from app.models.afe import (
    Afe,
    AfeConsumableLine,
    AfeServiceChargeLine,
    AfeServiceLine,
    AfeServiceRate,
    AfeServiceSectionRate,
    AfeTangibleLine,
)
from app.models.audit_log import AuditLog
from app.models.catalogue import (
    CatalogueConfig,
    ConsumableSubcategory,
    DrillBit,
    DrillBitRate,
    MudChemical,
    MudChemicalRate,
    Service,
    Tangible,
    TangibleRate,
)
from app.models.master_data import (
    Activity,
    Currency,
    HoleSection,
    Phase,
    PurchaseOrderServiceOrder,
    UnitOfMeasurement,
    VendorSupplier,
)
from app.models.rig_well import Rig, Well, WellPhase, WellSection
from app.models.role import Role
from app.models.user import User, user_roles
from app.models.well_sub_activity import WellSubActivity

__all__ = [
    "Activity",
    "Afe",
    "AfeConsumableLine",
    "AfeServiceChargeLine",
    "AfeServiceLine",
    "AfeServiceRate",
    "AfeServiceSectionRate",
    "AfeTangibleLine",
    "AuditLog",
    "CatalogueConfig",
    "ConsumableSubcategory",
    "Currency",
    "DrillBit",
    "DrillBitRate",
    "HoleSection",
    "MudChemical",
    "MudChemicalRate",
    "Phase",
    "PurchaseOrderServiceOrder",
    "Rig",
    "Role",
    "Service",
    "Tangible",
    "TangibleRate",
    "UnitOfMeasurement",
    "User",
    "VendorSupplier",
    "Well",
    "WellPhase",
    "WellSection",
    "WellSubActivity",
    "user_roles",
]
