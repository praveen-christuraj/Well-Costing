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
    ItemSubCategory,
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
        seen_order_numbers: set[str] = set()
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
                # Relaxation: procurement entities use order_number as unique key
                if entity in {"service-orders", "purchase-orders"}:
                    order_no = normalized.get("order_number")
                    if isinstance(order_no, str):
                        key = order_no.strip().upper()
                        if key in seen_order_numbers:
                            raise ValueError(
                                f"Duplicate order_number '{order_no}' within workbook "
                                f"(row {excel_row})"
                            )
                        seen_order_numbers.add(key)
                        # DB duplicate check - case-insensitive, friendly error instead of
                        # DB IntegrityError
                        model = ServiceOrder if entity == "service-orders" else PurchaseOrder
                        exists = self.session.scalar(
                            select(model).where(model.order_number.ilike(key))
                        )
                        if exists is not None:
                            raise ValueError(
                                f"order_number '{order_no}' already exists in database "
                                "- will be skipped on import"
                            )
                valid.append(normalized)
            except (ValueError, ValidationError, TypeError, InvalidOperation) as exc:
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
            self._stringify(values, ("order_number", "title", "status", "description"))
            # Relaxation: normalize order_number and status for bulk tolerance
            if "order_number" in values:
                values["order_number"] = str(values["order_number"]).strip().upper()
                if not values["order_number"]:
                    raise ValueError("order_number is required")
            if "status" in values:
                values["status"] = self._normalize_status(values["status"], "service")
            else:
                values["status"] = "draft"
            self._coerce_dates(values, ("valid_from", "valid_to"))
            self._coerce_decimal(values, "contract_value")
            # Empty string decimals should be treated as not set
            if values.get("contract_value") == "":
                values.pop("contract_value", None)
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
            self._stringify(values, ("order_number", "title", "status", "description"))
            if "order_number" in values:
                values["order_number"] = str(values["order_number"]).strip().upper()
                if not values["order_number"]:
                    raise ValueError("order_number is required")
            if "status" in values:
                values["status"] = self._normalize_status(values["status"], "purchase")
            else:
                values["status"] = "draft"
            self._coerce_dates(values, ("order_date", "expected_delivery_date"))
            self._coerce_decimal(values, "order_value")
            if values.get("order_value") == "":
                values.pop("order_value", None)
            return PurchaseOrderCreate.model_validate(values).model_dump(
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
            self._resolve_order(values, "purchase_order_number", "purchase_order_id", PurchaseOrder)
            values["item_id"] = self._resolve_item(values)
            self._stringify(values, ("item_type", "description"))
            self._coerce_dates(values, ("effective_from", "effective_to"))
            self._coerce_decimal(values, "unit_price")
            return ItemPriceCreate.model_validate(values).model_dump(mode="json", exclude_none=True)

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
                    ("sub_category_code", "sub_category_id", ItemSubCategory),
                ]
            )
        if entity == "services":
            values["rate_basis"] = self._normalize_rate_basis(values.get("rate_basis", "daily"))
        for source_field, target_field, model in mappings:
            code = values.pop(source_field, None)
            if code in (None, ""):
                continue
            # Case-insensitive code lookup
            code_str = str(code).strip()
            instance = self.session.scalar(select(model).where(model.code.ilike(code_str)))
            if instance is None:
                raise ValueError(f"{source_field} '{code}' does not exist")
            values[target_field] = instance.id

    @staticmethod
    def _normalize_rate_basis(value: Any) -> str:
        """Normalise free-text service rate basis labels to the stored enum."""
        if value in (None, ""):
            return "daily"
        raw = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        synonyms = {
            "daily_rate": "daily",
            "per_day": "daily",
            "per_section_rate": "per_section",
            "per_service_rate": "per_service",
            "fixed_rate": "fixed",
        }
        return synonyms.get(raw, raw)

    def _resolve_codes(
        self, values: dict[str, Any], mappings: list[tuple[str, str, type[Any]]]
    ) -> None:
        for source_field, target_field, model in mappings:
            code = values.pop(source_field, None)
            if code in (None, ""):
                continue
            # Case-insensitive lookup using ilike for flexible input matching
            code_str = str(code).strip()
            instance = self.session.scalar(select(model).where(model.code.ilike(code_str)))
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
        instance = self.session.scalar(select(model).where(model.order_number.ilike(number_str)))
        if instance is None:
            raise ValueError(f"{source_field} '{number}' does not exist")
        values[target_field] = instance.id

    def _resolve_item(self, values: dict[str, Any]) -> Any:
        item_code = values.pop("item_code", None)
        if item_code in (None, ""):
            raise ValueError("item_code is required")
        item_type = values.pop("item_type", None)
        # Case-insensitive lookup for item code
        statement = select(CatalogItem).where(CatalogItem.code.ilike(str(item_code).strip()))
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

    def _coerce_dates(self, values: dict[str, Any], fields: tuple[str, ...]) -> None:
        for field in fields:
            if field in values:
                values[field] = self._date(values[field])

    @staticmethod
    def _coerce_decimal(values: dict[str, Any], field: str) -> None:
        if field not in values:
            return
        value = values[field]
        if isinstance(value, Decimal):
            return
        if value in (None, ""):
            values.pop(field, None)
            return
        raw = (
            str(value)
            .strip()
            .replace(",", "")
            .replace("$", "")
            .replace("₹", "")
            .replace("€", "")
            .replace("£", "")
        )
        # Handle accounting parentheses: (1234.50) -> -1234.50
        if raw.startswith("(") and raw.endswith(")"):
            raw = "-" + raw[1:-1]
        raw = raw.strip()
        if raw == "" or raw == "-":
            values.pop(field, None)
            return
        try:
            values[field] = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError(f"{field} must be numeric (got '{value}')") from exc

    @staticmethod
    def _stringify(values: dict[str, Any], fields: tuple[str, ...]) -> None:
        for field in fields:
            if field not in values:
                continue
            value = values[field]
            if isinstance(value, float) and value.is_integer():
                values[field] = str(int(value))
            else:
                values[field] = str(value).strip()

    @staticmethod
    def _normalize_status(value: object, kind: str) -> str:
        """Relaxed status normalization: case-insensitive, whitespace-tolerant.

        Unknown values default to draft.
        """
        raw = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        service_allowed = {"draft", "active", "expired", "cancelled"}
        purchase_allowed = {"draft", "open", "partially_received", "closed", "cancelled"}
        allowed = service_allowed if kind == "service" else purchase_allowed
        # Common synonyms for relaxation
        synonyms = {
            "activated": "active",
            "enabled": "active",
            "in_progress": "open",
            "partial": "partially_received",
            "partiallyreceived": "partially_received",
            "closed_done": "closed",
            "canceled": "cancelled",
        }
        normalized = synonyms.get(raw, raw)
        if normalized in allowed:
            return normalized
        # Relaxation: unknown status coerced to draft instead of hard failure
        return "draft"

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
            # Excel serial date number - approximate from 1899-12-30 epoch
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
