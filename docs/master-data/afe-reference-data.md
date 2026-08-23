# AFE reference data

This is the raw data layer the Drilling and Completion AFEs are built from. Every
page is bulk-first: server-side pagination, filters designed for large volumes,
Excel-style inline entry, clipboard paste, and per-row Edit/Delete actions.

## Where each AFE input comes from

| AFE input | Page | Notes |
| --- | --- | --- |
| Companies providing services (3rd party and in-house) | **Vendors** | `vendor_type` distinguishes `third_party` from `inhouse`. |
| Service order numbers and contract validity | **Service Orders** | Reference register only — an order records the contract number, vendor, validity window, value, and status, and is never required to point at a service. |
| Service day rates — operating, standby, mob, demob | **Well rate book**, not master data | A service is priced per well: see [well-scoped rate governance](../architecture/well-rate-governance.md). |
| Section-wise service rates | **Well rate book** | Set `hole_section_id` on the well's service rate. |
| Services catalogue | **Catalogue Items** (`item_type = service`) | Directional, cementing, logging, surveys, and support services — identity only, no rate. |
| Item classification (bits, casings, shoes, wellheads…) | **Primary / Secondary / Tertiary Categories** | The single classification. Secondary is the item's category, Tertiary its sub category. |
| Tangibles (bits, casings, centralisers, plugs, pup joints…) | **Tangibles** | Includes material number, specification, and manufacturer. |
| Mud chemicals with UOM and unique numbers | **Mud Chemicals** | `material_number` carries the vendor/SAP unique number. |
| Cement additives with UOM and unique numbers | **Cement Additives** | Same shape as mud chemicals. |
| Tangible and consumable rates, with purchase orders | **Tangible Rates** | Effective-dated master rate per item, vendor, and PO. |
| History of every master rate change | **Rate Revisions** | Read-only log: amount before and after, effective date, actor, reason. |

## Data model

```text
vendors ──────────────┬─< service_orders
                      └─< purchase_orders ──< item_prices ──< rate_revisions
                                                   │
                                                   └── catalog_items (tangible / mud_chemical / cement_additive)

primary_categories ──< secondary_categories ──< tertiary_categories
                 └──────────────┬───────────────────────┘
                                └──< catalog_items (primary / secondary / tertiary)
                                └──< cost_categories (primary / secondary)

catalog_items (item_type='service') ── priced per well in well_service_rates
```

Services deliberately hold no master rate. The same crew is quoted differently
per well, per rig, and per campaign, and a central revision must never move the
cost basis of a well that is already drilling — so the rate is entered on the
well and frozen there. Tangible rates *are* held centrally, and a well copies
the rate in force when the item is picked.

### Vendors

Extends the existing register with `vendor_type` (`third_party` | `inhouse`),
`contact_person`, `email`, `phone`, and `country`. A check constraint rejects any
other vendor type.

### Classification

One hierarchy classifies everything: **Primary → Secondary → Tertiary**. The
former `item_categories` and `item_subcategories` tables are gone, and so is the
separate Services register — they were parallel classifications of the same
thing.

* **Primary Category** places the item: Services, Tangibles, Mud Chemicals,
  Cement Additives, and any level the operator adds.
* **Secondary Category** is the item's *category* — `BITS`, `CASING`,
  `CEMENTING`, `VISCOSIFIERS`.
* **Tertiary Category** is its *sub category* — `PDC`, `SURFACE-CASING`.

Choosing the deepest level is enough: the API derives the parents from it and
rejects a combination the hierarchy does not contain. Cost categories are filed
the same way — their parent is a Primary Category and their second level a
Secondary Category — so costing and catalogue data roll up together.

### Catalogue items

`catalog_items` carries `primary_category_id`, `secondary_category_id`,
`tertiary_category_id`, `material_number`, `specification`, and
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

The same shape applies to `/procurement/purchase-orders` and
`/procurement/item-prices`. Master rates are additionally revised, never
overwritten:

```text
POST /procurement/item-prices/{id}/revise    supersede with the next revision
GET  /procurement/rate-revisions             the master rate change log
```

### Filters

| Endpoint | Filters |
| --- | --- |
| `master-data/vendors` | `search`, `is_active`, `vendor_type` |
| `master-data/{catalogue}` | `search` (code, name, material number), `is_active`, `item_type`, `primary_category_id`, `secondary_category_id`, `tertiary_category_id`, `default_unit_id`, `cost_category_id`, `cost_code_id` |
| `master-data/primary-categories` | `search`, `is_active` |
| `master-data/secondary-categories` | `search`, `is_active`, `primary_category_id` |
| `master-data/tertiary-categories` | `search`, `is_active`, `secondary_category_id` |
| `procurement/service-orders` | `search`, `is_active`, `vendor_id`, `status`, `valid_on` |
| `procurement/purchase-orders` | `search`, `is_active`, `vendor_id`, `status` |
| `procurement/rate-revisions` | `item_id`, `change_type` |
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
