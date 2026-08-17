# AFE reference data

This is the raw data layer the Drilling and Completion AFEs are built from. Every
page is bulk-first: server-side pagination, filters designed for large volumes,
Excel-style inline entry, clipboard paste, and per-row Edit/Delete actions.

## Where each AFE input comes from

| AFE input | Page | Notes |
| --- | --- | --- |
| Companies providing services (3rd party and in-house) | **Vendors** | `vendor_type` distinguishes `third_party` from `inhouse`. |
| Service order numbers and contract validity | **Service Orders** | Contract number, vendor, validity window, contract value, status. |
| Service day rates — operating, standby, mob, demob | **Service Rates** | One row per service/vendor holds all four rates as columns. |
| Section-wise rates | **Service Rates** | Set `hole_section` (for example `12-1/4"`) on the rate row. |
| Services catalogue | **Services** | Directional, cementing, logging, surveys, and support services. |
| Tangible categories (bits, casings, shoes, wellheads…) | **Item Categories** | Scoped by `applies_to`. |
| Tangibles (bits, casings, centralisers, plugs, pup joints…) | **Tangibles** | Includes material number, specification, and manufacturer. |
| Mud chemicals with UOM and unique numbers | **Mud Chemicals** | `material_number` carries the vendor/SAP unique number. |
| Cement additives with UOM and unique numbers | **Cement Additives** | Same shape as mud chemicals. |
| Tangible and consumable rates, with purchase orders | **Item Prices** | Effective-dated unit price per item, vendor, and PO. |

## Data model

```text
vendors ──────────────┬─< service_orders ──< service_rate_cards >── catalog_items (item_type='service')
                      └─< purchase_orders ──< item_prices        >── catalog_items (tangible / mud_chemical / cement_additive)

item_categories ──< catalog_items
```

### Vendors

Extends the existing register with `vendor_type` (`third_party` | `inhouse`),
`contact_person`, `email`, `phone`, and `country`. A check constraint rejects any
other vendor type.

### Item categories

`item_categories` classifies catalogue items — `BITS`, `CASING`, `CENTRALISER`,
`SHOE-COLLAR`, `PLUGS`, `WELLHEAD`, `PUPJOINT`, `PIPTAG`, and consumable groups.
The `applies_to` column scopes a category to `service`, `tangible`,
`mud_chemical`, or `cement_additive`, so each page only offers relevant options.

### Catalogue items

`catalog_items` gains `item_category_id`, `material_number`, `specification`, and
`manufacturer`. Two new polymorphic subtypes join services, tangibles, materials,
and equipment:

- `mud_chemical` → `/api/v1/master-data/mud-chemicals`
- `cement_additive` → `/api/v1/master-data/cement-additives`

`material_number` holds the vendor or SAP unique number and is included in the
free-text search on every catalogue page.

### Service rate cards

`service_rate_cards` stores one row per service, vendor, and effective period,
with each rate type as its own column — mirroring the source workbook:

| Column | Meaning |
| --- | --- |
| `operating_rate` | Rate while operating |
| `standby_rate` | Rate while on standby |
| `mobilisation_rate` | One-off mobilisation charge |
| `demobilisation_rate` | One-off demobilisation charge |
| `hole_section` | Optional section scope; blank means all sections |
| `service_order_id` | The contract the rate is drawn from |

Rates are effective-dated (`effective_from` / `effective_to`), so historical AFEs
stay reproducible. `service_id` must reference an item whose `item_type` is
`service`; anything else is rejected with HTTP 422.

### Item prices

`item_prices` holds effective-dated unit prices for tangibles and consumables,
each linked to a vendor and, optionally, a purchase order.

## API

All routes sit under `/api/v1` and require a bearer token.

```text
GET    /master-data/{entity}                 paginated + filtered list
POST   /master-data/{entity}                 create one
PATCH  /master-data/{entity}/{id}            update one
DELETE /master-data/{entity}/{id}            deactivate (add ?hard=true to delete)
POST   /master-data/{entity}/bulk/validate   dry-run validation
POST   /master-data/{entity}/bulk/create     all-or-nothing create
PATCH  /master-data/{entity}/bulk/update     all-or-nothing update

GET|POST         /procurement/service-orders
GET|PATCH|DELETE /procurement/service-orders/{id}
POST             /procurement/service-orders/bulk/{validate,create}
PATCH            /procurement/service-orders/bulk/update
```

The same shape applies to `/procurement/purchase-orders`, `/procurement/service-rates`,
and `/procurement/item-prices`.

### Filters

| Endpoint | Filters |
| --- | --- |
| `master-data/vendors` | `search`, `is_active`, `vendor_type` |
| `master-data/{catalogue}` | `search` (code, name, material number), `is_active`, `item_category_id`, `default_unit_id`, `cost_category_id`, `cost_code_id` |
| `master-data/item-categories` | `search`, `is_active`, `applies_to` |
| `procurement/service-orders` | `search`, `is_active`, `vendor_id`, `status`, `valid_on` |
| `procurement/purchase-orders` | `search`, `is_active`, `vendor_id`, `status` |
| `procurement/service-rates` | `search`, `is_active`, `service_id`, `vendor_id`, `service_order_id`, `hole_section`, `effective_on` |
| `procurement/item-prices` | `search`, `is_active`, `item_id`, `item_type`, `vendor_id`, `purchase_order_id`, `effective_on` |

`valid_on` and `effective_on` return only records whose date window covers the
supplied date, which is how an AFE picks the rate applicable on a given day.

Every list endpoint accepts `page`, `page_size` (max 500), `sort_by`, and
`sort_order`, and returns `{ items, page, page_size, total, pages }`.

## Deletion behaviour

`DELETE` deactivates by default, preserving the audit trail. `?hard=true`
permanently removes the record, but the API returns **409 Conflict** when the
record is still referenced — a vendor used by a rate card cannot be erased. The
UI tries a hard delete first and automatically falls back to deactivation,
reporting which action it took.

## Excel round trips

Every entity has a mapping profile with column aliases, so real workbooks import
without being reformatted. `mob`, `mob_rate`, and `mobilisation_rate` all resolve
to the same field, and codes (`vendor_code`, `service_code`, `po_number`) are
resolved to identifiers during validation.

```text
GET  /import/{entity}/template   blank versioned template
POST /import/{entity}/preview    validate and stage, no writes
POST /import/{entity}/commit     all-or-nothing commit
GET  /export/{entity}            current data as .xlsx
```

Bumping a profile's columns bumps its version; `vendors` is now `1.1`.

Because export and import share one mapping profile, an exported workbook can be
edited and re-imported unchanged — the round trip is covered by
`backend/tests/integration/test_excel_import.py::test_export_reimport_round_trip`.

## Export and print

Every Master Data grid exposes **Export** and **Print** in its action bar.

- **Export** downloads `GET /export/{entity}` as `{entity}-export.xlsx`. The grid
  supplies the entity through `export-entity`, so a page only names its registry
  key; `on-export` remains available when a page needs a bespoke handler.
- **Print** opens the browser print dialog against a print-only rendering of the
  loaded rows — a plain table without editors, toolbars, filters, or the actions
  column, printed A4 landscape with repeating headers. `Ctrl+P` produces the same
  sheet, and select values, numeric formatting, unit/currency suffixes, and
  active/inactive states all render as text.

Export reflects the whole entity; print reflects the rows currently loaded in the
grid, so filters and page size narrow what is printed.

## Migration

`20260814_0012_add_procurement_and_consumable_master_data` creates the new tables
and extends `vendors` and `catalog_items`. Apply with:

```powershell
cd backend
alembic upgrade head
```
