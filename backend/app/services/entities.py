"""Named service classes backed by the shared cost-library workflow."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.services.master_data import MasterDataService


class UnitService(MasterDataService):
    def __init__(self, session: Session, actor_id: UUID) -> None:
        super().__init__(session, "units", actor_id)


class CurrencyService(MasterDataService):
    def __init__(self, session: Session, actor_id: UUID) -> None:
        super().__init__(session, "currencies", actor_id)


class CostCategoryService(MasterDataService):
    def __init__(self, session: Session, actor_id: UUID) -> None:
        super().__init__(session, "cost-categories", actor_id)


class CostCodeService(MasterDataService):
    def __init__(self, session: Session, actor_id: UUID) -> None:
        super().__init__(session, "cost-codes", actor_id)


class VendorService(MasterDataService):
    def __init__(self, session: Session, actor_id: UUID) -> None:
        super().__init__(session, "vendors", actor_id)


class ServiceService(MasterDataService):
    def __init__(self, session: Session, actor_id: UUID) -> None:
        super().__init__(session, "services", actor_id)


class TangibleService(MasterDataService):
    def __init__(self, session: Session, actor_id: UUID) -> None:
        super().__init__(session, "tangibles", actor_id)


class MaterialService(MasterDataService):
    def __init__(self, session: Session, actor_id: UUID) -> None:
        super().__init__(session, "materials", actor_id)


class EquipmentService(MasterDataService):
    def __init__(self, session: Session, actor_id: UUID) -> None:
        super().__init__(session, "equipment", actor_id)
