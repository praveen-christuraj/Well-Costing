"""Row-level Excel validation and reference resolution."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master_data import CatalogItem, CostCategory, CostCode, Currency, Unit, Vendor
from app.schemas.master_data import BulkRowError, MasterDataCreate, RateCreate
from app.services.master_data import ENTITY_CONFIGS


@dataclass(frozen=True)
class ValidationResult:
    valid_rows: list[dict[str, Any]]
    errors: list[BulkRowError]
    total_rows: int


class ExcelValidator:
    def __init__(self, session: Session) -> None:
        self.session = session

    def validate(self, entity: str, rows: list[dict[str, Any]]) -> ValidationResult:
        valid: list[dict[str, Any]] = []
        errors: list[BulkRowError] = []
        seen_codes: set[str] = set()
        for index, source in enumerate(rows):
            excel_row = index + 2
            try:
                normalized = self._normalize(entity, source)
                code = normalized.get("code")
                if isinstance(code, str):
                    if code in seen_codes:
                        raise ValueError("Duplicate code within workbook")
                    seen_codes.add(code)
                    config = ENTITY_CONFIGS.get(entity)
                    if config is not None:
                        statement = select(config.model).where(config.model.code == code)  # type: ignore[attr-defined]
                        if self.session.scalar(statement) is not None:
                            raise ValueError(f"Code '{code}' already exists")
                valid.append(normalized)
            except (ValueError, ValidationError) as exc:
                errors.append(
                    BulkRowError(
                        row_index=excel_row,
                        code="row_validation_error",
                        message=str(exc),
                    )
                )
        return ValidationResult(valid, errors, len(rows))

    def _normalize(self, entity: str, source: dict[str, Any]) -> dict[str, Any]:
        values = {key: value for key, value in source.items() if value not in (None, "")}
        if "is_active" in values:
            values["is_active"] = self._boolean(values["is_active"])
        if entity == "rates":
            values = self._rate_values(values)
            return RateCreate.model_validate(values).model_dump(mode="json")

        if entity not in ENTITY_CONFIGS:
            raise ValueError(f"Unsupported entity '{entity}'")
        if "code" in values:
            values["code"] = str(values["code"]).strip().upper()
        if "name" in values:
            values["name"] = str(values["name"]).strip()
        self._resolve_master_references(entity, values)
        return MasterDataCreate.model_validate(values).model_dump(mode="json", exclude_none=True)

    def _resolve_master_references(self, entity: str, values: dict[str, Any]) -> None:
        mappings: list[tuple[str, str, type[Any]]] = []
        if entity == "cost-categories":
            mappings.append(("parent_code", "parent_id", CostCategory))
        if entity == "cost-codes":
            mappings.append(("cost_category_code", "cost_category_id", CostCategory))
        if entity in {"services", "tangibles", "materials", "equipment"}:
            mappings.extend(
                [
                    ("cost_category_code", "cost_category_id", CostCategory),
                    ("cost_code", "cost_code_id", CostCode),
                    ("default_unit_code", "default_unit_id", Unit),
                ]
            )
        for source_field, target_field, model in mappings:
            code = values.pop(source_field, None)
            if code in (None, ""):
                continue
            instance = self.session.scalar(
                select(model).where(model.code == str(code).strip().upper())
            )
            if instance is None:
                raise ValueError(f"{source_field} '{code}' does not exist")
            values[target_field] = instance.id

    def _rate_values(self, values: dict[str, Any]) -> dict[str, Any]:
        item_code = str(values.pop("item_code")).strip().upper()
        item_type = values.pop("item_type", None)
        statement = select(CatalogItem).where(CatalogItem.code == item_code)
        if item_type:
            statement = statement.where(CatalogItem.item_type == str(item_type).strip().lower())
        items = list(self.session.scalars(statement).all())
        if len(items) != 1:
            raise ValueError(
                f"item_code '{item_code}' must resolve to exactly one item; "
                "supply item_type if ambiguous"
            )
        values["item_id"] = items[0].id
        for source_field, target_field, model in [
            ("vendor_code", "vendor_id", Vendor),
            ("currency_code", "currency_id", Currency),
            ("unit_code", "unit_id", Unit),
        ]:
            code = str(values.pop(source_field)).strip().upper()
            instance = self.session.scalar(select(model).where(model.code == code))
            if instance is None:
                raise ValueError(f"{source_field} '{code}' does not exist")
            values[target_field] = instance.id
        try:
            values["amount"] = Decimal(str(values["amount"]))
        except InvalidOperation as exc:
            raise ValueError("amount must be numeric") from exc
        for field in ("effective_from", "effective_to"):
            if field in values:
                values[field] = self._date(values[field])
        return values

    @staticmethod
    def _boolean(value: object) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"true", "yes", "y", "1", "active"}:
            return True
        if normalized in {"false", "no", "n", "0", "inactive"}:
            return False
        raise ValueError(f"Cannot interpret '{value}' as a boolean")

    @staticmethod
    def _date(value: object) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value).strip())
        except ValueError as exc:
            raise ValueError(f"'{value}' is not an ISO date") from exc
