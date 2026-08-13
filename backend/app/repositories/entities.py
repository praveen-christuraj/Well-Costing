"""Named repository classes for discoverable master-data boundaries."""

from sqlalchemy.orm import Session

from app.models.master_data import (
    CostCategory,
    CostCode,
    Currency,
    Equipment,
    Material,
    Service,
    Tangible,
    Unit,
    Vendor,
)
from app.repositories.master_data import MasterDataRepository


class UnitRepository(MasterDataRepository[Unit]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Unit)


class CurrencyRepository(MasterDataRepository[Currency]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Currency)


class CostCategoryRepository(MasterDataRepository[CostCategory]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, CostCategory)


class CostCodeRepository(MasterDataRepository[CostCode]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, CostCode)


class VendorRepository(MasterDataRepository[Vendor]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Vendor)


class ServiceRepository(MasterDataRepository[Service]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Service)


class TangibleRepository(MasterDataRepository[Tangible]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Tangible)


class MaterialRepository(MasterDataRepository[Material]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Material)


class EquipmentRepository(MasterDataRepository[Equipment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Equipment)
