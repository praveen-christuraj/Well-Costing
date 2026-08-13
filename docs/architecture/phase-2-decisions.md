# Phase 2 architecture decisions

## ADR-006 — Catalogue item supertype

**Status:** Accepted for Phase 2  
**Date:** 2026-08-12

Services, tangibles, materials, and equipment use joined relational subtypes of `catalog_items`. Rates reference the supertype with a real foreign key. This avoids a non-relational `entity_type + entity_id` reference while retaining separate business entities and APIs.

## ADR-007 — Deactivate instead of destructive delete

**Status:** Provisional audit-safety policy  
**Date:** 2026-08-12

Phase 2 `DELETE` sets `is_active=false`. Historical rates and future estimates must not lose referenced master data. Final retention/restore behavior remains subject to business confirmation.

## ADR-008 — Versioned code mapping in application configuration

**Status:** Accepted for available Phase 2 evidence  
**Date:** 2026-08-12

Mapping profiles are named/versioned Python configuration with explicit aliases and API overrides. They are not arbitrary executable formulas. Persisted administrator-editable mapping profiles may be added after actual workbook mappings are certified.

## ADR-009 — No rate overlap rule yet

**Status:** Accepted deferral  
**Date:** 2026-08-12

The database validates date range direction but does not reject overlapping item/vendor/currency/unit ranges. Selection precedence is a costing business rule and remains unimplemented until workbook/business evidence confirms it.
