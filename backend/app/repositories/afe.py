"""Persistence queries for Phase 3 afe intake."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.afe import Afe, AfeLine, Project, Well


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, project_id: UUID) -> Project | None:
        return self.session.get(Project, project_id)

    def get_by_code(self, code: str) -> Project | None:
        return self.session.scalar(select(Project).where(Project.code == code))

    def list(
        self, page: int, page_size: int, search: str | None, is_active: bool | None
    ) -> tuple[Sequence[Project], int]:
        statement = select(Project)
        count = select(func.count()).select_from(Project)
        if search:
            pattern = f"%{search}%"
            clause = or_(Project.code.ilike(pattern), Project.name.ilike(pattern))
            statement, count = statement.where(clause), count.where(clause)
        if is_active is not None:
            statement, count = (
                statement.where(Project.is_active == is_active),
                count.where(Project.is_active == is_active),
            )
        statement = statement.order_by(Project.code).offset((page - 1) * page_size).limit(page_size)
        return self.session.scalars(statement).all(), int(self.session.scalar(count) or 0)


class WellRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, well_id: UUID) -> Well | None:
        return self.session.get(Well, well_id)

    def list(
        self,
        page: int,
        page_size: int,
        search: str | None,
        project_id: UUID | None,
        is_active: bool | None,
    ) -> tuple[Sequence[Well], int]:
        statement = select(Well)
        count = select(func.count()).select_from(Well)
        clauses: list[ColumnElement[bool]] = []
        if search:
            pattern = f"%{search}%"
            clauses.append(or_(Well.code.ilike(pattern), Well.name.ilike(pattern)))
        if project_id:
            clauses.append(Well.project_id == project_id)
        if is_active is not None:
            clauses.append(Well.is_active == is_active)
        if clauses:
            statement, count = statement.where(*clauses), count.where(*clauses)
        statement = statement.order_by(Well.code).offset((page - 1) * page_size).limit(page_size)
        return self.session.scalars(statement).unique().all(), int(self.session.scalar(count) or 0)


class AfeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, afe_id: UUID) -> Afe | None:
        return self.session.get(Afe, afe_id)

    def list(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        project_id: UUID | None,
        well_id: UUID | None,
        status: str | None,
        is_active: bool | None,
    ) -> tuple[Sequence[Afe], int]:
        statement = select(Afe).join(Well).join(Project)
        count = select(func.count()).select_from(Afe).join(Well).join(Project)
        clauses: list[ColumnElement[bool]] = []
        if search:
            pattern = f"%{search}%"
            clauses.append(
                or_(
                    Afe.code.ilike(pattern),
                    Afe.title.ilike(pattern),
                    Well.code.ilike(pattern),
                    Project.code.ilike(pattern),
                )
            )
        if project_id:
            clauses.append(Project.id == project_id)
        if well_id:
            clauses.append(Well.id == well_id)
        if status:
            clauses.append(Afe.status == status)
        if is_active is not None:
            clauses.append(Afe.is_active == is_active)
        if clauses:
            statement, count = statement.where(*clauses), count.where(*clauses)
        statement = (
            statement.order_by(Afe.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return self.session.scalars(statement).unique().all(), int(self.session.scalar(count) or 0)


class AfeLineRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, item_id: UUID) -> AfeLine | None:
        return self.session.get(AfeLine, item_id)

    def list_for_afe(self, afe_id: UUID) -> Sequence[AfeLine]:
        statement = select(AfeLine).where(AfeLine.afe_id == afe_id).order_by(AfeLine.line_number)
        return self.session.scalars(statement).unique().all()
