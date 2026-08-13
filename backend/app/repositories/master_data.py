"""Generic typed repositories for the Phase 2 cost library."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.master_data import CatalogItem, Rate


class MasterDataRepository[ModelT: Base]:
    """Shared SQLAlchemy CRUD with safe filtering and sorting."""

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def get(self, item_id: UUID) -> ModelT | None:
        return self.session.get(self.model, item_id)

    def get_by_code(self, code: str) -> ModelT | None:
        statement = select(self.model).where(self.model.code == code.strip().upper())  # type: ignore[attr-defined]
        return self.session.scalar(statement)

    def list(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        is_active: bool | None,
        sort_by: str,
        sort_order: str,
    ) -> tuple[Sequence[ModelT], int]:
        statement = select(self.model)
        count_statement = select(func.count()).select_from(self.model)
        filters: list[Any] = []
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    self.model.code.ilike(pattern),  # type: ignore[attr-defined]
                    self.model.name.ilike(pattern),  # type: ignore[attr-defined]
                )
            )
        if is_active is not None:
            filters.append(self.model.is_active == is_active)  # type: ignore[attr-defined]
        if filters:
            statement = statement.where(*filters)
            count_statement = count_statement.where(*filters)

        allowed_sort = {"code", "name", "created_at", "updated_at", "is_active"}
        resolved_sort = sort_by if sort_by in allowed_sort else "code"
        column = getattr(self.model, resolved_sort)
        statement = statement.order_by(column.desc() if sort_order == "desc" else column.asc())
        statement = statement.offset((page - 1) * page_size).limit(page_size)
        return self.session.scalars(statement).unique().all(), int(
            self.session.scalar(count_statement) or 0
        )

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        self.session.flush()
        self.session.refresh(instance)
        return instance

    def delete(self, instance: ModelT) -> None:
        self.session.delete(instance)
        self.session.flush()


class CatalogItemRepository(MasterDataRepository[CatalogItem]):
    def get_by_typed_code(self, item_type: str, code: str) -> CatalogItem | None:
        statement = select(CatalogItem).where(
            CatalogItem.item_type == item_type,
            CatalogItem.code == code.strip().upper(),
        )
        return self.session.scalar(statement)


class RateRepository(MasterDataRepository[Rate]):
    def list(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        is_active: bool | None,
        sort_by: str,
        sort_order: str,
    ) -> tuple[Sequence[Rate], int]:
        del search
        statement = select(Rate)
        count_statement = select(func.count()).select_from(Rate)
        if is_active is not None:
            statement = statement.where(Rate.is_active == is_active)
            count_statement = count_statement.where(Rate.is_active == is_active)
        allowed = {"amount", "effective_from", "effective_to", "created_at", "updated_at"}
        column = getattr(Rate, sort_by if sort_by in allowed else "effective_from")
        statement = statement.order_by(column.desc() if sort_order == "desc" else column.asc())
        statement = statement.offset((page - 1) * page_size).limit(page_size)
        return self.session.scalars(statement).unique().all(), int(
            self.session.scalar(count_statement) or 0
        )
