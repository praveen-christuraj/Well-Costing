"""Safe tabular workbook reader for Excel and CSV uploads."""

import csv
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO, StringIO
from itertools import zip_longest
from pathlib import Path
from typing import Any

import xlrd
from openpyxl import load_workbook

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
        selected_sheet_name = sheet_name or "first sheet"
        try:
            if extension in CSV_EXTENSIONS:
                columns, records = self._read_csv(content)
            elif extension == ".xls":
                columns, records, selected_sheet_name = self._read_xls(content, sheet_name)
            else:
                columns, records, selected_sheet_name = self._read_xlsx_like(content, sheet_name)
        except BusinessValidationError:
            raise
        except Exception as exc:
            raise BusinessValidationError(
                "File could not be read", {"reason": str(exc)}
            ) from exc
        return WorkbookRows(
            columns=columns,
            rows=records,
            sheet_name=selected_sheet_name,
        )

    @staticmethod
    def _read_csv(content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
        """Parse CSV bytes, tolerating BOM and common delimiters."""

        text: str | None = None
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None or not text.strip():
            raise BusinessValidationError("CSV file is empty or uses an unsupported encoding")
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","

        reader = csv.reader(StringIO(text), delimiter=delimiter)
        rows = list(reader)
        if not rows:
            raise BusinessValidationError("CSV file is empty")

        columns = [str(column).strip() for column in rows[0]]
        records = [
            {
                str(key): ExcelReader._python_value(value)
                for key, value in zip_longest(columns, row, fillvalue=None)
                if key is not None
            }
            for row in rows[1:]
        ]
        return columns, records

    @staticmethod
    def _read_xlsx_like(
        content: bytes, sheet_name: str | None
    ) -> tuple[list[str], list[dict[str, Any]], str]:
        workbook = load_workbook(filename=BytesIO(content), data_only=True, read_only=True)
        try:
            if sheet_name:
                if sheet_name not in workbook.sheetnames:
                    raise BusinessValidationError(
                        "Requested sheet not found", {"sheet_name": sheet_name}
                    )
                sheet = workbook[sheet_name]
                selected_sheet_name = sheet_name
            else:
                sheet = workbook[workbook.sheetnames[0]]
                selected_sheet_name = str(sheet.title)

            iterator = sheet.iter_rows(values_only=True)
            header_row = next(iterator, None)
            if header_row is None:
                raise BusinessValidationError("Workbook sheet is empty")

            columns = [str(column).strip() for column in header_row]
            records = [
                {
                    str(key): ExcelReader._python_value(value)
                    for key, value in zip_longest(columns, row, fillvalue=None)
                    if key is not None
                }
                for row in iterator
            ]
            return columns, records, selected_sheet_name
        finally:
            workbook.close()

    @staticmethod
    def _read_xls(
        content: bytes, sheet_name: str | None
    ) -> tuple[list[str], list[dict[str, Any]], str]:
        workbook = xlrd.open_workbook(file_contents=content)
        if workbook.nsheets == 0:
            raise BusinessValidationError("Workbook has no sheets")

        if sheet_name:
            try:
                sheet = workbook.sheet_by_name(sheet_name)
            except xlrd.biffh.XLRDError as exc:
                raise BusinessValidationError(
                    "Requested sheet not found", {"sheet_name": sheet_name}
                ) from exc
            selected_sheet_name = sheet_name
        else:
            sheet = workbook.sheet_by_index(0)
            selected_sheet_name = str(sheet.name)

        if sheet.nrows == 0:
            raise BusinessValidationError("Workbook sheet is empty")

        columns = [str(column).strip() for column in sheet.row_values(0)]
        records: list[dict[str, Any]] = []
        for row_index in range(1, sheet.nrows):
            row_values = sheet.row_values(row_index)
            record: dict[str, Any] = {}
            for key, value in zip_longest(columns, row_values, fillvalue=None):
                if key is None:
                    continue
                record[str(key)] = ExcelReader._python_value(value)
            records.append(record)

        return columns, records, selected_sheet_name

    @staticmethod
    def _python_value(value: object) -> object:
        if isinstance(value, datetime):
            return value
        if value == "":
            return None
        if hasattr(value, "to_pydatetime"):
            return value.to_pydatetime()  # type: ignore[union-attr]
        if hasattr(value, "item"):
            try:
                return value.item()  # type: ignore[union-attr]
            except (TypeError, ValueError):
                return value
        return value
