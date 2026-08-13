"""Excel import history persistence."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.import_tracking import ImportBatch


class ImportBatchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, batch_id: UUID) -> ImportBatch | None:
        return self.session.get(ImportBatch, batch_id)

    def add(self, batch: ImportBatch) -> ImportBatch:
        self.session.add(batch)
        self.session.flush()
        self.session.refresh(batch)
        return batch

    def list(self, page: int, page_size: int) -> tuple[Sequence[ImportBatch], int]:
        statement = (
            select(ImportBatch)
            .order_by(ImportBatch.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        total = int(self.session.scalar(select(func.count()).select_from(ImportBatch)) or 0)
        return self.session.scalars(statement).unique().all(), total
