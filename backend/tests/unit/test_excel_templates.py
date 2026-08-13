"""Excel template generation tests."""

from io import BytesIO

import pytest
from app.core.exceptions import BusinessValidationError, NotFoundError
from app.integrations.excel.reader import ExcelReader
from app.integrations.excel.templates import ExcelTemplateService
from openpyxl import load_workbook


def test_requirement_template_has_versioned_profile_headers() -> None:
    content = ExcelTemplateService().create_blank("requirement-items")
    workbook = load_workbook(BytesIO(content))
    sheet = workbook.active
    assert sheet is not None
    headers = [cell.value for cell in sheet[1]]
    assert headers[:6] == [
        "line_number",
        "catalog_item_code",
        "item_type",
        "cost_code",
        "quantity",
        "unit_code",
    ]
    assert sheet.freeze_panes == "A2"


def test_unknown_template_fails_clearly() -> None:
    with pytest.raises(NotFoundError, match="No Excel template"):
        ExcelTemplateService().create_blank("unknown")


def test_reader_rejects_unsupported_file_types() -> None:
    with pytest.raises(BusinessValidationError, match="Unsupported workbook extension"):
        ExcelReader().read(b"not-a-workbook", "requirements.csv")
