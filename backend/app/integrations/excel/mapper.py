"""Versioned configurable Excel column mappings."""

from dataclasses import dataclass
from typing import Any

from app.core.exceptions import BusinessValidationError


def normalize_header(value: str) -> str:
    return "_".join(value.strip().lower().replace("/", " ").replace("-", " ").split())


@dataclass(frozen=True)
class MappingProfile:
    name: str
    version: str
    required: frozenset[str]
    aliases: dict[str, frozenset[str]]

    @property
    def headers(self) -> list[str]:
        return list(self.aliases)


COMMON_ALIASES = {
    "code": frozenset({"code", "item_code", "vendor_code", "uom_code", "currency_code"}),
    "name": frozenset({"name", "description_name", "item_name"}),
    "description": frozenset({"description", "details", "remarks"}),
    "is_active": frozenset({"is_active", "active", "status"}),
}
CATALOG_ALIASES = {
    **COMMON_ALIASES,
    "cost_category_code": frozenset({"cost_category_code", "cost_category", "category_code"}),
    "cost_code": frozenset({"cost_code", "expense_code"}),
    "default_unit_code": frozenset({"default_unit_code", "unit", "uom"}),
}
PROFILE_REGISTRY: dict[str, MappingProfile] = {
    "units": MappingProfile(
        "units-default",
        "1.0",
        frozenset({"code", "name"}),
        {**COMMON_ALIASES, "symbol": frozenset({"symbol", "abbreviation"})},
    ),
    "currencies": MappingProfile(
        "currencies-default",
        "1.0",
        frozenset({"code", "name"}),
        {**COMMON_ALIASES, "symbol": frozenset({"symbol", "currency_symbol"})},
    ),
    "cost-categories": MappingProfile(
        "cost-categories-default",
        "1.0",
        frozenset({"code", "name"}),
        {**COMMON_ALIASES, "parent_code": frozenset({"parent_code", "parent_category"})},
    ),
    "cost-codes": MappingProfile(
        "cost-codes-default",
        "1.0",
        frozenset({"code", "name", "cost_category_code"}),
        {
            **COMMON_ALIASES,
            "cost_category_code": frozenset({"cost_category_code", "category_code"}),
        },
    ),
    "vendors": MappingProfile(
        "vendors-default", "1.0", frozenset({"code", "name"}), COMMON_ALIASES
    ),
    "services": MappingProfile(
        "services-default", "1.0", frozenset({"code", "name"}), CATALOG_ALIASES
    ),
    "tangibles": MappingProfile(
        "tangibles-default", "1.0", frozenset({"code", "name"}), CATALOG_ALIASES
    ),
    "materials": MappingProfile(
        "materials-default", "1.0", frozenset({"code", "name"}), CATALOG_ALIASES
    ),
    "equipment": MappingProfile(
        "equipment-default", "1.0", frozenset({"code", "name"}), CATALOG_ALIASES
    ),
    "estimate-items": MappingProfile(
        "estimate-items-default",
        "1.0",
        frozenset({"line_number", "quantity", "unit_code"}),
        {
            "line_number": frozenset({"line_number", "line", "row"}),
            "item_code": frozenset({"item_code", "catalog_item_code"}),
            "item_type": frozenset({"item_type", "cost_type"}),
            "cost_code": frozenset({"cost_code", "expense_code"}),
            "vendor_code": frozenset({"vendor_code", "vendor"}),
            "rate_id": frozenset({"rate_id", "rate_uuid"}),
            "quantity": frozenset({"quantity", "qty"}),
            "unit_code": frozenset({"unit_code", "unit", "uom"}),
            "notes": frozenset({"notes", "remarks"}),
        },
    ),
    "requirement-items": MappingProfile(
        "requirement-items-default",
        "1.0",
        frozenset(
            {
                "line_number",
                "catalog_item_code",
                "item_type",
                "cost_code",
                "quantity",
                "unit_code",
            }
        ),
        {
            "line_number": frozenset({"line_number", "line", "row"}),
            "catalog_item_code": frozenset({"catalog_item_code", "item_code", "service_code"}),
            "item_type": frozenset({"item_type", "cost_type"}),
            "cost_code": frozenset({"cost_code", "expense_code"}),
            "quantity": frozenset({"quantity", "qty"}),
            "unit_code": frozenset({"unit_code", "unit", "uom"}),
            "section_name": frozenset({"section_name", "section", "hole_section"}),
            "planned_duration_days": frozenset(
                {"planned_duration_days", "planned_days", "duration_days"}
            ),
            "planned_depth_from": frozenset({"planned_depth_from", "depth_from"}),
            "planned_depth_to": frozenset({"planned_depth_to", "planned_depth", "depth_to"}),
            "depth_unit_code": frozenset({"depth_unit_code", "depth_unit"}),
            "notes": frozenset({"notes", "remarks"}),
            "is_active": COMMON_ALIASES["is_active"],
        },
    ),
    "cost-control-lines": MappingProfile(
        "cost-control-lines-default",
        "1.0",
        frozenset(
            {
                "transaction_date",
                "source_document_type",
                "source_document_reference",
                "cost_code",
                "description",
                "currency_code",
                "amount",
            }
        ),
        {
            "transaction_date": frozenset({"transaction_date", "date", "posting_date"}),
            "source_document_type": frozenset(
                {"source_document_type", "document_type", "source_type"}
            ),
            "source_document_reference": frozenset(
                {"source_document_reference", "document_reference", "document_number"}
            ),
            "external_transaction_id": frozenset(
                {"external_transaction_id", "external_id", "transaction_id"}
            ),
            "cost_code": frozenset({"cost_code", "expense_code"}),
            "vendor_code": frozenset({"vendor_code", "vendor"}),
            "description": frozenset({"description", "details", "remarks"}),
            "quantity": frozenset({"quantity", "qty"}),
            "unit_code": frozenset({"unit_code", "unit", "uom"}),
            "currency_code": frozenset({"currency_code", "currency"}),
            "amount": frozenset({"amount", "transaction_amount", "cost"}),
            "correction_kind": frozenset({"correction_kind", "correction_type", "entry_type"}),
            "reverses_transaction_id": frozenset({"reverses_transaction_id", "reversal_of"}),
        },
    ),
    "rates": MappingProfile(
        "rates-default",
        "1.0",
        frozenset(
            {"item_code", "vendor_code", "currency_code", "unit_code", "amount", "effective_from"}
        ),
        {
            "item_code": frozenset(
                {"item_code", "service_code", "material_code", "equipment_code"}
            ),
            "item_type": frozenset({"item_type", "cost_type"}),
            "vendor_code": frozenset({"vendor_code", "vendor"}),
            "currency_code": frozenset({"currency_code", "currency"}),
            "unit_code": frozenset({"unit_code", "unit", "uom"}),
            "amount": frozenset({"amount", "rate", "unit_rate", "price"}),
            "effective_from": frozenset({"effective_from", "start_date", "effective_date"}),
            "effective_to": frozenset({"effective_to", "end_date", "expiry_date"}),
            "description": COMMON_ALIASES["description"],
            "is_active": COMMON_ALIASES["is_active"],
        },
    ),
}


@dataclass(frozen=True)
class MappedRows:
    rows: list[dict[str, Any]]
    detected_columns: list[str]
    applied_mapping: dict[str, str]
    profile: MappingProfile


class ExcelMapper:
    def map(
        self,
        entity: str,
        columns: list[str],
        rows: list[dict[str, Any]],
        overrides: dict[str, str] | None = None,
    ) -> MappedRows:
        try:
            profile = PROFILE_REGISTRY[entity]
        except KeyError as exc:
            raise BusinessValidationError(f"No mapping profile exists for '{entity}'") from exc

        alias_to_target: dict[str, str] = {}
        for target, aliases in profile.aliases.items():
            for alias in aliases | {target}:
                alias_to_target[normalize_header(alias)] = target

        applied: dict[str, str] = {}
        targets: set[str] = set()
        normalized_overrides = {
            normalize_header(source): target for source, target in (overrides or {}).items()
        }
        for source in columns:
            normalized = normalize_header(source)
            target = normalized_overrides.get(normalized) or alias_to_target.get(normalized)
            if target is None:
                continue
            if target not in profile.aliases:
                raise BusinessValidationError(f"Mapping target '{target}' is not allowed")
            if target in targets:
                raise BusinessValidationError(
                    f"Multiple source columns map to '{target}'. Confirm the mapping explicitly."
                )
            applied[source] = target
            targets.add(target)

        missing = profile.required - targets
        if missing:
            raise BusinessValidationError(
                "Required workbook columns are missing",
                {"missing": sorted(missing), "detected": columns},
            )

        mapped = [
            {target: row.get(source) for source, target in applied.items()}
            for row in rows
            if any(value not in (None, "") for value in row.values())
        ]
        return MappedRows(mapped, columns, applied, profile)
