"""Framework-neutral Excel read-map-validate pipeline orchestration."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.integrations.excel.mapper import ExcelMapper, MappingProfile
from app.integrations.excel.reader import ExcelReader
from app.integrations.excel.validator import ExcelValidator, ValidationResult


@dataclass(frozen=True)
class ImportPipelinePreview:
    detected_columns: list[str]
    applied_mapping: dict[str, str]
    profile: MappingProfile
    validation: ValidationResult
    mapped_rows: list[dict[str, Any]]


class ExcelImportPipeline:
    """Execute read → map → validate without committing business records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def preview(
        self,
        *,
        entity: str,
        filename: str,
        content: bytes,
        sheet_name: str | None = None,
        mapping_overrides: dict[str, str] | None = None,
    ) -> ImportPipelinePreview:
        workbook = ExcelReader().read(content, filename, sheet_name)
        mapped = ExcelMapper().map(entity, workbook.columns, workbook.rows, mapping_overrides)
        validation = ExcelValidator(self.session).validate(entity, mapped.rows)
        return ImportPipelinePreview(
            detected_columns=mapped.detected_columns,
            applied_mapping=mapped.applied_mapping,
            profile=mapped.profile,
            validation=validation,
            mapped_rows=mapped.rows,
        )
