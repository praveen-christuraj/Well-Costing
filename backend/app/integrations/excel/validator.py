"""Row-level Excel validation and reference resolution."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master_data import (
    CatalogItem,
    CostCategory,
    CostCode,
    Currency,
    ItemCategory,
    PurchaseOrder,
    ServiceOrder,
    Unit,
    Vendor,
)
from app.schemas.master_data import BulkRowError, MasterDataCreate, RateCreate
from app.schemas.procurement import (
    ItemPriceCreate,
    PurchaseOrderCreate,
    ServiceOrderCreate,
    ServiceRateCardCreate,
)
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
        if entity == "service-orders":
            self._resolve_codes(
                values,
                [
                    ("vendor_code", "vendor_id", Vendor),
                    ("currency_code", "currency_id", Currency),
                ],
            )
            return ServiceOrderCreate.model_validate(values).model_dump(
                mode="json", exclude_none=True
            )
        if entity == "purchase-orders":
            self._resolve_codes(
                values,
                [
                    ("vendor_code", "vendor_id", Vendor),
                    ("currency_code", "currency_id", Currency),
                ],
            )
            return PurchaseOrderCreate.model_validate(values).model_dump(
                mode="json", exclude_none=True
            )
        if entity == "service-rates":
            self._resolve_codes(
                values,
                [
                    ("vendor_code", "vendor_id", Vendor),
                    ("currency_code", "currency_id", Currency),
                    ("unit_code", "unit_id", Unit),
                ],
            )
            self._resolve_order(values, "service_order_number", "service_order_id", ServiceOrder)
            service_code = values.pop("service_code", None)
            if service_code in (None, ""):
                raise ValueError("service_code is required")
            service = self.session.scalar(
                select(CatalogItem).where(
                    CatalogItem.code == str(service_code).strip().upper(),
                    CatalogItem.item_type == "service",
                )
            )
            if service is None:
                raise ValueError(f"service_code '{service_code}' does not exist")
            values["service_id"] = service.id
            return ServiceRateCardCreate.model_validate(values).model_dump(
                mode="json", exclude_none=True
            )
        if entity == "item-prices":
            self._resolve_codes(
                values,
                [
                    ("vendor_code", "vendor_id", Vendor),
                    ("currency_code", "currency_id", Currency),
                    ("unit_code", "unit_id", Unit),
                ],
            )
            self._resolve_order(
                values, "purchase_order_number", "purchase_order_id", PurchaseOrder
            )
            values["item_id"] = self._resolve_item(values)
            return ItemPriceCreate.model_validate(values).model_dump(
                mode="json", exclude_none=True
            )

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
        if entity in {
            "services",
            "tangibles",
            "materials",
            "equipment",
            "mud-chemicals",
            "cement-additives",
        }:
            mappings.extend(
                [
                    ("cost_category_code", "cost_category_id", CostCategory),
                    ("cost_code", "cost_code_id", CostCode),
                    ("default_unit_code", "default_unit_id", Unit),
                    ("item_category_code", "item_category_id", ItemCategory),
                ]
            )
        for source_field, target_field, model in mappings:
            code = values.pop(source_field, None)
            if code in (None, ""):
                continue
            # Case-insensitive code lookup
            code_str = str(code).strip()
            instance = self.session.scalar(
                select(model).where(model.code.ilike(code_str))
            )
            if instance is None:
                raise ValueError(f"{source_field} '{code}' does not exist")
            values[target_field] = instance.id

    def _resolve_codes(
        self, values: dict[str, Any], mappings: list[tuple[str, str, type[Any]]]
    ) -> None:
        for source_field, target_field, model in mappings:
            code = values.pop(source_field, None)
            if code in (None, ""):
                continue
            # Case-insensitive lookup using ilike for flexible input matching
            code_str = str(code).strip()
            instance = self.session.scalar(
                select(model).where(model.code.ilike(code_str))
            )
            if instance is None:
                raise ValueError(f"{source_field} '{code}' does not exist")
            values[target_field] = instance.id

    def _resolve_order(
        self, values: dict[str, Any], source_field: str, target_field: str, model: type[Any]
    ) -> None:
        number = values.pop(source_field, None)
        if number in (None, ""):
            return
        # Case-insensitive order number lookup
        number_str = str(number).strip()
        instance = self.session.scalar(
            select(model).where(model.order_number.ilike(number_str))
        )
        if instance is None:
            raise ValueError(f"{source_field} '{number}' does not exist")
        values[target_field] = instance.id

    def _resolve_item(self, values: dict[str, Any]) -> Any:
        item_code = values.pop("item_code", None)
        if item_code in (None, ""):
            raise ValueError("item_code is required")
        item_type = values.pop("item_type", None)
        # Case-insensitive lookup for item code
        statement = select(CatalogItem).where(
            CatalogItem.code.ilike(str(item_code).strip())
        )
        if item_type:
            statement = statement.where(
                CatalogItem.item_type == str(item_type).strip().lower().replace("-", "_")
            )
        items = list(self.session.scalars(statement).all())
        if len(items) != 1:
            raise ValueError(
                f"item_code '{item_code}' must resolve to exactly one item; "
                "supply item_type if ambiguous"
            )
        return items[0].id

    def _rate_values(self, values: dict[str, Any]) -> dict[str, Any]:
        item_code = str(values.pop("item_code")).strip()
        item_type = values.pop("item_type", None)
        # Case-insensitive item code lookup
        statement = select(CatalogItem).where(CatalogItem.code.ilike(item_code))
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
            code = str(values.pop(source_field)).strip()
            # Case-insensitive code lookup
            instance = self.session.scalar(select(model).where(model.code.ilike(code)))
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
        """Parse a date value from Excel with relaxed format handling.

        Accepts Python datetime/date objects, ISO-8601 strings, and common
        date formats: DD/MM/YYYY, MM/DD/YYYY, DD-MM-YYYY, DD.MM.YYYY,
        YYYY/MM/DD, YYYYMMDD, and date-only Excel serial numbers (as int).
        """
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, (int, float)):
            # Excel serial date number – approximate from 1899-12-30 epoch
            from datetime import timedelta
            try:
                return date(1899, 12, 30) + timedelta(days=int(value))
            except (OverflowError, ValueError):
                raise ValueError(f"'{value}' is not a valid Excel serial date") from None
        raw = str(value).strip()
        # Try ISO format first (YYYY-MM-DD)
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
        # Try common date formats
        separators = r"[/\-\.]"
        patterns = [
            (r"^(\d{4})" + separators + r"(\d{1,2})" + separators + r"(\d{1,2})$", "%Y-%m-%d"),
            (r"^(\d{1,2})" + separators + r"(\d{1,2})" + separators + r"(\d{4})$", "%d-%m-%Y"),
            (r"^(\d{4})(\d{2})(\d{2})$", "%Y-%m-%d"),
            (r"^(\d{2})(\d{2})(\d{4})$", "%m-%d-%Y"),
        ]
        for pattern, fmt in patterns:
            match = re.match(pattern, raw)
            if match:
                parts = match.groups()
                reconstructed = f"{parts[0]}-{parts[1]}-{parts[2]}"
                try:
                    parsed = datetime.strptime(reconstructed, fmt)
                    return parsed.date()
                except ValueError:
                    continue
        raise ValueError(
            f"'{value}' is not a recognised date format. "
            "Use YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, or DD-MM-YYYY."
        )
