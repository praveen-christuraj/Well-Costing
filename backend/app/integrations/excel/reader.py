"""Safe tabular Excel workbook reader."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.exceptions import BusinessValidationError

ALLOWED_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
MAX_WORKBOOK_BYTES = 15 * 1024 * 1024


@dataclass(frozen=True)
class WorkbookRows:
    columns: list[str]
    rows: list[dict[str, Any]]
    sheet_name: str


class ExcelReader:
    """Read one workbook sheet into JSON-compatible row dictionaries."""

    def read(self, content: bytes, filename: str, sheet_name: str | None = None) -> WorkbookRows:
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise BusinessValidationError(
                f"Unsupported workbook extension '{extension}'. Use .xlsx, .xlsm, or .xls."
            )
        if len(content) > MAX_WORKBOOK_BYTES:
            raise BusinessValidationError("Workbook exceeds the 15 MB Phase 2 upload limit")
        try:
            selected_sheet: str | int = sheet_name if sheet_name else 0
            frame = pd.read_excel(  # pyright: ignore[reportUnknownMemberType]
                BytesIO(content), sheet_name=selected_sheet, dtype=object
            )
        except Exception as exc:
            raise BusinessValidationError(
                "Workbook could not be read", {"reason": str(exc)}
            ) from exc

        frame.columns = [str(column).strip() for column in frame.columns]
        frame = frame.where(pd.notna(frame), None)
        records = [
            {str(key): self._python_value(value) for key, value in row.items()}
            for row in frame.to_dict(orient="records")
        ]
        return WorkbookRows(
            columns=list(frame.columns),
            rows=records,
            sheet_name=sheet_name or "first sheet",
        )

    @staticmethod
    def _python_value(value: object) -> object:
        if hasattr(value, "to_pydatetime"):
            return value.to_pydatetime()  # type: ignore[union-attr]
        if hasattr(value, "item"):
            try:
                return value.item()  # type: ignore[union-attr]
            except (TypeError, ValueError):
                return value
        return value
