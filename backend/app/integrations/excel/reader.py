"""Safe tabular workbook reader for Excel and CSV uploads."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.exceptions import BusinessValidationError

EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
CSV_EXTENSIONS = {".csv"}
ALLOWED_EXTENSIONS = EXCEL_EXTENSIONS | CSV_EXTENSIONS
MAX_WORKBOOK_BYTES = 15 * 1024 * 1024


@dataclass(frozen=True)
class WorkbookRows:
    columns: list[str]
    rows: list[dict[str, Any]]
    sheet_name: str


class ExcelReader:
    """Read one workbook sheet or CSV file into JSON-compatible row dictionaries."""

    def read(self, content: bytes, filename: str, sheet_name: str | None = None) -> WorkbookRows:
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise BusinessValidationError(
                f"Unsupported file extension '{extension}'. Use .xlsx, .xlsm, .xls, or .csv."
            )
        if len(content) > MAX_WORKBOOK_BYTES:
            raise BusinessValidationError("Upload exceeds the 15 MB limit")
        try:
            if extension in CSV_EXTENSIONS:
                frame = self._read_csv(content)
            else:
                selected_sheet: str | int = sheet_name if sheet_name else 0
                frame = pd.read_excel(  # pyright: ignore[reportUnknownMemberType]
                    BytesIO(content), sheet_name=selected_sheet, dtype=object
                )
        except BusinessValidationError:
            raise
        except Exception as exc:
            raise BusinessValidationError(
                "File could not be read", {"reason": str(exc)}
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
    def _read_csv(content: bytes) -> pd.DataFrame:
        """Parse CSV bytes, tolerating BOM and both comma/semicolon delimiters."""

        text: str | None = None
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None or not text.strip():
            raise BusinessValidationError("CSV file is empty or uses an unsupported encoding")
        from io import StringIO

        return pd.read_csv(  # pyright: ignore[reportUnknownMemberType]
            StringIO(text), dtype=object, sep=None, engine="python"
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
