# Changelog

All notable project changes are documented here.

## 2026-08-27 — Working Import buttons with fill-and-upload templates; category-dependent tangible subcategories

### Fixed

- The **Import** button on every Master Data / Services / Consumables /
  Tangibles tab opened nothing: the shared import dialog bound PrimeVue's
  `Dialog` with `v-model`, but the component toggles visibility through
  `visible` (`v-model:visible`). The dialog now opens on every tab.
- The manage-dialog **Bulk Add** for dropdown lists called a path the API did
  not register (`/configs/{type}/bulk`); the route now exists and accepts the
  dialog's payload.

### Added

- **Download → fill → upload import loop.** Every importable module (UOM,
  Currencies, Phases, Activities, Hole Sections, Vendors, PO/SO, Services,
  Mud Chemicals, Drill Bits, Tangibles) serves a styled XLSX template from
  `/import-template`: header row matching the parser, in-cell dropdowns for
  enum columns (scope, category, provider type, UOM, currency, vendor code,
  PO type, Yes/No), and an Instructions sheet with example rows. The Import
  dialog gained numbered steps, drag & drop, extension/15 MB validation and an
  "import another file" reset — an untouched template imports zero rows.
- **Tangible subcategories depend on categories.** `catalogue_configs` gains
  `parent_value` (migration `20260827_0006`); the Subcategories manage dialog
  requires picking the category first, lists/adds values per category, allows
  the same name under different categories, and can move legacy unassigned
  values under a category. In the Tangibles grid the Subcategory dropdown
  only offers values configured under the row's Category (changing the
  category clears an invalid subcategory), and the API rejects or re-validates
  mismatched pairs on create, update and bulk import.

## 2026-08-27 — Currency backfill fits VARCHAR(10) on UUID primary keys

`alembic upgrade head` aborted on Termux with
`psycopg.errors.StringDataRightTruncation: value too long for type character varying(10)`
while running `20260827_0004`. A pre-restructure `currencies` table can keep UUID
primary keys; the backfill concatenated `C` with the full UUID
(`Cfe8f4fe6-14dd-4eab-a8fb-a9ae2d367477`, 37 characters) into
`currency_code VARCHAR(10)`.

### Fixed

- Unique `*_code` placeholders are sized to the live column. Integer ids still
  produce short codes (`C1`); UUID ids hash into the available width so
  PostgreSQL no longer rejects the update.
- The same helper is used when `20260827_0002` adds a missing code column onto
  a legacy table, so both paths survive UUID primary keys.

## 2026-08-27 — One-off cleanup of the pre-restructure tables

Databases provisioned before the module restructure still carried the removed modules'
tables (AFE, AFE Cost Estimates, Daily Cost, Well Activities, Cost Control, Cost Builder,
Reports, Assurance) while `alembic_version` pointed at a revision of the deleted history —
a state neither `upgrade head` nor `downgrade base` can reconcile.

### Added

- `backend/scripts/temp_clean_database.py`, a **temporary** maintenance helper (delete it
  once the databases are clean; `docs/database/overview.md` keeps the manual procedure).
  It classifies every table/view in the target schema against `app/models`, drops what the
  code no longer references, recreates the application's own tables through
  `alembic upgrade head` when they cannot be reconciled in place (so `alembic_version`
  ends up stamped correctly instead of `create_all`-built), and finishes with the same
  drift check `/health` reports. Dry run by default; `--execute --confirm CLEAN` applies,
  `--backup-dir` exports a CSV plus DDL of everything being destroyed first, `--keep`
  spares named tables, `--prune-only` drops nothing but the stale objects, and hosted
  environments are refused unless `--allow-hosted` is passed. Reads `DATABASE_URL` from the
  backend settings, so it embeds no credentials.

## 2026-08-27 — Master Data 500s, login audit, print sheets, and Add row

Currency, Activities, Hole Sections and the other catalogues returned a generic
500 ("An unexpected error occurred") when listing legacy rows with NULL required
strings, or when saving a row without a symbol. Print dumped the whole shell
including data-entry controls. The audit page still used Tailwind classes this
app does not load, and a successful sign-in wrote no audit row.

### Fixed

- List/create/update for every master-data module tolerate NULL legacy columns,
  ignore unknown payload keys, default a missing symbol to the code, and restore
  a soft-deleted row when the same code is created again — so those tabs load
  and save instead of 500ing.
- Integrity/data errors return 409/400 instead of an opaque 500.
- Print emits a dedicated sheet (title, filter line, read-only table) and hides
  the shell, toolbars, editors and paginator. Ctrl+P uses the same layout.
- Audit Log restyled to the current PageHeader / card / compact-table shell.

### Added

- Successful sign-in writes a `LOGIN` audit row (failed attempts do not).
- **Add row** on every catalogue grid, so a single entry no longer requires
  creating five rows and deleting four. **+5 Rows** remains for bulk entry.
- Migration `20260827_0004` backfills NULL symbols/names on existing tables.
- Master-data and audit tables are registered in `CRITICAL_SCHEMA` so `/health`
  reports drift instead of leaving list endpoints to fail.

## 2026-08-27 — Migrations survive partially provisioned databases

`alembic upgrade head` aborted with
`psycopg.errors.DuplicateTable: relation "currencies" already exists` on
deployments whose database already held the master-data tables while
`alembic_version` still pointed at `20260827_0001` (a Termux phone upgraded
across the history reset). The upgrade could neither move forward nor roll
back, so `termux/deploy.sh` failed every run.

### Added

- `app/db/migration_ops.py` — idempotent DDL helpers (`create_table_if_missing`,
  `create_index_if_missing`, `add_missing_columns`, and their drop
  counterparts). Existing tables are left in place, missing columns are added
  (backfilled from their server default when the backend rejects adding a
  defaulted `NOT NULL` column), and existing indexes are skipped.
- `backend/tests/integration/test_migrations.py` — covers a clean upgrade, a
  replay over already-created tables, and an older table that is missing
  columns while keeping its rows.

### Changed

- Revisions `20260827_0001` and `20260827_0002` use the idempotent helpers, so
  re-running them converges an existing database instead of failing.
- `termux/lib-debian-backend.sh` explains a `DuplicateTable` migration failure
  (pull the latest deploy; otherwise use an empty database or
  `alembic stamp head`) alongside the existing connection/auth diagnostics.

## 2026-08-27 — Restructure to an authenticated empty shell

### Removed

- **Every business module.** Master Data catalogues (primary/secondary/tertiary
  categories, activities, cost codes, cost categories, units, vendors,
  materials, services, tangibles, currencies, hole sections, drilling phases,
  item prices, rate revisions, purchase orders, service orders), AFE, AFE Cost
  Estimates, Daily Cost, Well Activities, Cost Analytics, Cost Control, Reports,
  Assurance, Audit Log, Administration › Dropdown Sources and Help are gone —
  pages, components, composables, services, stores, types and utilities.
- **Backend modules.** The `afe`, `afe_estimates`, `afe_snapshots`, `assurance`,
  `audit`, `calculations`, `cost_control`, `daily_cost`, `enterprise_config`,
  `estimates`, `imports`, `master_data`, `procurement`, `rates`, `reference`,
  `reporting`, `well_activities`, `well_costing` and `workflow` routes, with
  their services, repositories, models and Pydantic schemas. The whole
  `app/domain/` costing package and the `app/integrations/excel/` import/export
  boundary are deleted, along with the `openpyxl` and `xlrd` dependencies.
- **Database tables.** Every table outside `users`, `roles` and `user_roles` —
  projects, wells, AFEs and AFE lines/sections/snapshots/audit logs, estimates
  and versions, daily cost entries and lines, cost control staging and
  transactions, the classification hierarchy, well activities, the catalogue and
  its rates/revisions, procurement orders, enterprise configuration, workflow
  profiles, reporting mappings and export attempts, import tracking, and the
  global audit log.
- **Module tests, documentation and fixtures.** Excel sample workbooks and
  scenario data (`test_data/`), the phase reports, business-rule registers,
  database/module specs, and the reporting contract.
- Login no longer writes an audit-log row; the audit module it called is gone.

### Changed

- **Breaking — database.** The Alembic history was reset. The 28 revisions that
  built the removed modules are replaced by a single baseline,
  `20260827_0001_create_auth_tables`. A database that already carries the old
  tables cannot be upgraded onto it: drop and recreate the schema (or provision
  a fresh database) and run `alembic upgrade head`.
- `CRITICAL_SCHEMA` in `app/db/schema.py` now covers only `users`, `roles` and
  `user_roles`. A rebuilt module must register its tables there or schema drift
  goes unreported by `/health`.
- The API surface is `GET /live`, `GET /health`, `GET /ready`,
  `POST /auth/login`, `GET /auth/me`. Nothing else is routed.
- Business-rule exception types (`business_rule_pending`,
  `workflow_profile_pending`, `afe_policy_pending`, `cost_state_policy_pending`,
  `business_validation_error`) were dropped from the error envelope.
- The sidebar now lists Dashboard and Master Data only; the topbar's Help link
  is gone. The dashboard reports API, database, schema and version state instead
  of AFE and Daily Cost figures.
- `echarts` is no longer a frontend dependency.
- Docs reduced to shell-level architecture, database, API, deployment and
  testing. ADR-005/006/007 are marked superseded by the new ADR-008.

### Added

- `pages/master-data/index.vue` — an intentionally empty Master Data stub that
  the rebuilt catalogues hang off.
- ADR-008 recording the restructure decision and what a rebuilt module must
  provide.

## 2026-08-26 — Submitted AFE pricing and scope-only consumables

### Changed

- AFE Lines now keep only the current scope: classification, cost code, type, rate basis, section and notes. The compact grid no longer asks for consumable usage/day, planned quantity, or UOM.
- Consumables use a per-unit estimated rate in **AFE Cost Estimates**. Their actual quantity and UOM are entered only in **Daily Cost** for the operational day.
- **AFE Cost Estimates** now accepts and lists submitted AFEs only, enforced in both the selector and the API. Draft AFEs return a clear workflow validation message instead of a generic error.
- Scope-only AFE lines with no UOM now load correctly in AFE Cost Estimates; a current line's saved estimate rate is its estimated amount.
- AFE and AFE Cost Estimate printouts/exports now use only the current AFE → AFE Cost Estimate chain and omit retired usage/quantity columns. The obsolete AFE-line Excel import/export router is no longer registered.
- AFE Lines and AFE Cost Estimate tables were compacted, with smaller selectors and larger viewport-aware table areas to reduce scrolling.

### Audit

- AFE line create, update, delete and recovery actions now include before/after scope detail in the global audit log and concise AFE-local history.
- Estimate-rate saves include rate-level before/after snapshots. AFE print, AFE Cost Estimate print and AFE Cost Estimate export are now recorded in the global audit log and AFE history.

## 2026-08-25 — Active AFE-to-Daily-Cost reporting chain

### Changed

- AFE Cost Estimates no longer infer or display hard-coded service/tangible/other types. They show the Primary and Secondary classifications configured by the user, and calculation behaviour comes from the selected rate basis.
- Daily Cost lines now retain a direct AFE-line reference and the backend resolves their default rate from AFE Cost Estimates, including classification-only AFE lines with no legacy catalogue item.
- Cost Control, Cost Analytics, the Dashboard and Reports read AFE, AFE Cost Estimates, Daily Cost and Well Activities directly. Retired Cost Builder, estimate snapshot, workflow and staging APIs are no longer registered in the active API router.
- Reports now generates AFE Register, AFE Cost Estimate Detail, Daily Cost Register, Cost Performance, and Well Activities & Accountability reports with live filters, print and Excel export.
- Audit Log now prints and exports the complete filtered result. Assurance checks the active source chain.

### Removed

- Retired Cost Library/Cost Builder frontend pages, components, services, stores and navigation; the old Enterprise Setup page is also removed from the released shell.
- Obsolete Cost Builder, staging, pending-report and enterprise-setup styles.

### Migration

- `20260825_0027` links operational and quantity Daily Cost lines to `afe_lines` and makes historical catalogue-item references optional.

## 2026-08-24 — Section-phase planning, all-sections rates, and full AFE print

### Added

- **Section → Phase planning hierarchy.** An AFE section is now defined by its
  hole section and depth interval, and the operational phases inside it are
  entered as child rows (`afe_section_phases`). A section's planned days are
  derived as the sum of its phases' planned days, and the AFE's total planned
  days are the sum of all sections. The AFE dialog shows each section with its
  expandable phase rows (add / remove phases), with live section and AFE
  totals. Daily Cost comparison now rolls planned days up phase-by-phase so
  actual days can be tracked against each planned phase.
- **All-sections service rates.** An AFE line can be flagged "Applies to every
  section", so a common service (e.g. a rig day rate) is entered once instead
  of being duplicated per section. The section reference is ignored while the
  flag is set, and AFE Cost Estimates group these lines under "All sections".
- **Full AFE printout.** The AFE page's Print now shows AFE number, well name,
  rig name, and project name; sections, planned depth, and planned days with
  the phase breakdown; a services table with unit/fixed rates and estimated
  costs; a tangibles table with unit rate, estimated consumption, and
  estimated costs; and a cost summary with Total Service Costs, Total Tangibles
  Cost, and Total Costs (rates pulled live from AFE Cost Estimates).
- Migration `20260824_0025` adds `afe_section_phases` and
  `afe_lines.applies_to_all_sections`.

### Changed

- `afe_sections.planned_days` and `afes.total_planned_days` are now derived on
  save from the phase plan instead of being typed directly. Legacy
  single-phase sections continue to work unchanged.

## 2026-08-24 — Confirmed deletion flows and complete audit coverage

### Added

- **Daily Cost deletion flow.** Saved day logs now have an explicit, confirmed
  soft-delete action. Deleted logs are removed from analytics, remain available
  under Deleted Day Logs for recovery, and cannot be silently reactivated by a
  later save.
- **Well Activity lifecycle.** Sub-activities now use audited create/update,
  soft-delete, and recover operations. The Well Activities page confirms both
  unsaved row removal and persisted deletion, hides deleted selectors, and offers
  recovery.
- **Audit detail snapshots.** Daily Cost updates record before/after totals and
  replaced line IDs; AFE section edits record before/after section plans. The
  global audit log now also receives well-scoped rates, unplanned items,
  enterprise configuration, imports, reporting exports, calculation attempts,
  workflow transitions, and cost-control actions.

### Changed

- Every destructive UI action now requires confirmation, including AFE section
  and unsaved-line removal, daily service/consumable line removal, legacy cost
  library deactivation controls, dropdown reset, and bulk deactivation.
- Permanent-delete fallback only deactivates when the API explicitly reports a
  reference conflict; network or authorization failures are no longer converted
  into a different write.

## 2026-08-23 — AFE Cost Estimates, mandatory activity accounting, and cost analytics

The cost builder is replaced by **AFE Cost Estimates** — the pricing side of the
AFE backbone. The AFE defines *what* the well plans (services, chemicals,
additives, tangibles, sections, phases, quantities); the AFE Cost Estimates page
prices *each AFE line* with a well-scoped unit rate. Daily cost entry reads its
unit rates from the AFE Cost Estimates only (per-line override still available
and recorded), must carry the day's activity type (Planned / NPT / UPA
sub-activity from the Well Activities page), and everything rolls up into a
well-scoped planned-versus-actual comparison.

### Added

- **AFE Cost Estimates** (`/afe-cost-estimates`, `afe_cost_estimate_lines`
  table, `/api/v1/afes/{afe_id}/cost-estimate` endpoints). Grabs the AFE lines
  exactly as entered on the AFE page and stores one well-scoped unit rate per
  line, with optional vendor and remarks. Live totals by hole section, item
  type, cost code, and rate basis; variance to the AFE budget; Excel export and
  a record-quality print layout with a signature block.
- **AFE print.** The AFE page now prints a well-scoped AFE record (header,
  sections & phases, lines) alongside the existing Excel export.
- **Daily cost reports.** Per-day printable report and Excel day report
  (`GET …/daily-cost/report?entry_date=`), plus a full daily cost register
  export (`GET …/daily-cost/export`) with entry, service-line, and
  consumable-line sheets.
- **Cost Analytics** (`/daily-cost/comparison`,
  `GET …/daily-cost/comparison[/export]`). Well-scoped planned-versus-actual
  comparison — section-wise (planned from the estimate vs actual), activity-wise
  (Planned / NPT / UPA and sub-activities with responsible parties), phase-wise
  (planned vs actual days), date-wise with planned cumulative, cumulative,
  week-wise, and month-wise — as charts, tables, and a multi-sheet Excel export.
- **Services register.** `master-data/services` page joins Tangibles, Mud
  Chemicals, and Cement Additives in the Catalogue group.

### Changed

- **Daily cost unit rates** now come from the AFE Cost Estimates of the well's
  governing AFE — not from catalogue or well rate books. The reference-rates
  endpoint reports the source AFE and how many AFE lines are still unpriced.
- **Daily cost entry requires the day's activity type.** Saving without a
  well-scoped sub-activity (configured on the Well Activities page) is refused,
  so Planned / NPT / UPA accounting can never be skipped; line-level activities
  must belong to the same well.
- **Navigation.** "Cost Builder" is replaced by "AFE Cost Estimates" under
  Planning; "Cost Analytics" joins Execution.

### Removed

- **All Catalogue Items page.** The unified register duplicated what the
  Primary → Secondary → Tertiary classification pages already provide; the
  catalogue group now lists Services, Tangibles, Mud Chemicals, and Cement
  Additives directly.
- **Cost builder pages.** The versioned bulk cost-build API remains for the
  workflow/cost-control chain, but its UI is superseded by AFE Cost Estimates.

## 2026-08-23 — One classification, and a configurable dropdown registry

Item categories and item sub categories were a second classification of the same
data the Primary → Secondary → Tertiary hierarchy already describes, so they are
gone and the hierarchy is now the only way anything is classified. On top of
that, which master-data section feeds which dropdown is no longer decided in
page code: every picker resolves through a registry a super administrator can
repoint.

### Added

- **Dropdown source registry.** Named *slots* (`afe.line.item`,
  `daily_cost.sub_activity`, …) and registered *sources* are declared in
  `app/domain/reference/`; the `dropdown_bindings` table holds the super-admin
  overrides on top. Slots carry a default source in code, so a database with no
  bindings behaves correctly, and each slot restricts which sources it accepts —
  the AFE line classification pickers can only ever read the classification.
  Structural slots (well-scoped sub-activities, the classification cascade) are
  locked. New endpoints under `/api/v1/reference`, and a console at
  **Administration › Dropdown Sources**. See
  [the registry documentation](docs/master-data/dropdown-source-registry.md).
- **Unified catalogue register.** `master-data/catalog-items` maintains every
  rate-bearing item in one place, with `item_type` naming the kind of item.
- **Delete impact preview.** `GET /master-data/{entity}/{id}/delete-impact`
  reports what a permanent delete would take with it. Deleting a tangible now
  removes its master rates and rate revisions — after a prompt stating the exact
  counts — and is refused outright while that history exists unless the cascade
  was confirmed.
- **Inline sub-activity configuration.** Sub-activities are created from the
  Daily Cost page, where they are needed, instead of only on a separate screen.

### Changed

- **Catalogue classification.** `catalog_items` gains `primary_category_id` and
  `secondary_category_id` alongside the existing `tertiary_category_id`. An
  item's category is its Secondary Category and its sub category its Tertiary
  Category. Supplying the deepest level is enough: the API derives the parents
  and rejects a combination the hierarchy does not contain.
- **Cost categories** take their parent from a Primary Category and their second
  level from a Secondary Category. The self-referencing parent is no longer
  offered anywhere in the UI.
- **AFE lines** are built strictly from the classification: Primary Category →
  Secondary Category → item, with the item list narrowed by the selection.
- **Phases inside the AFE.** The "Configure Phases" dialog is removed; AFE
  sections and daily cost entries read the phase list straight from master data.
- **Service and purchase orders** are documented and presented as reference
  registers. Nothing requires an order to be linked to a service or an item.
- **Master Data navigation** drops the Item Categories, Item Sub Categories, and
  Services tabs and groups the catalogue pages together.

### Removed

- `item_categories` and `item_subcategories` tables, models, routes, Excel
  mapping profiles, and pages. Migration `20260823_0023` converts existing item
  categories into secondary categories and the sub categories actually in use
  into tertiary categories, so no classification a user entered is lost.

## 2026-08-21 — Schema-drift self-healing, actionable 503s, and SQLite migrations

The 500s on `/afes`, `/wells`, `/projects`, and `/estimates` had two roots and
both are closed. A database left behind the application's migrations made every
planning endpoint fail with a generic "An unexpected error occurred"; migration
`20260821_0018` had also shipped `afe_audit_logs` without the `updated_at`
column the model selects, so even a fully migrated database failed the same
four endpoints (every AFE query eagerly loads its audit log). Now the backend
keeps the local database current itself, and when the schema is behind it says
so instead of 500ing.

### Added

- **Development auto-migration.** In `development`/`termux` environments the
  backend applies pending Alembic migrations on startup (opt out with
  `AUTO_MIGRATE=false`), and `start-dev.sh` runs `alembic upgrade head` before
  boot like the Windows script already did. A pulled update can no longer
  strand a local database behind the code.
- **Schema drift detection.** Startup and `/health` (and `/ready`, which now
  returns 503) compare the live database against the migration head and a set
  of critical planning tables/columns (`afes`, `afe_lines`, `wells`,
  `cost_estimates`, …) and report `database: "schema_outdated"` with the exact
  remediation. The dashboard shows a warning banner with the message.
- **Actionable errors.** Database "missing table/column" errors on any
  endpoint now return `503 {"error": {"code": "database_schema_outdated", …}}`
  with the migration command to run, instead of a generic 500.
- **Migration `20260821_0019`** adds the missing `afe_audit_logs.updated_at`
  column for databases that already applied 0018.
- **SQLite migrations reach head — and round-trip.** The SQLite dev path was
  broken in several places: the reporting-contract views used the reserved
  word `transaction` as a table alias (0010/0017), several migrations tried to
  add constraints to existing tables (unsupported by SQLite;
  0012/0016/0017/0018), SQLite refused the batch rebuilds of view-referenced
  tables (`wells` in 0015) and index recreation over dropped columns
  (`service_rate_cards` in 0014), and `PRAGMA legacy_alter_table` leaked
  between migrations and stopped the AFE table renames from retargeting
  foreign keys. The views use a `txn` alias, constraint DDL is
  dialect-guarded (catalogue checks on SQLite are swapped by safe table
  rebuilds), the pragma is set and restored explicitly where rebuilds need
  it, and `server_default` uses `func.now()` so defaults work on every
  dialect. `alembic upgrade head` → `downgrade base` → `upgrade head` now
  completes on SQLite (covered by a regression test); the 0012 downgrade also
  restores the originally named `ck_catalog_items_valid_item_type` check on
  PostgreSQL.

### Changed

- **List serializers tolerate orphaned records.** Hard-deleted projects,
  wells, AFEs, or currencies no longer crash the wells/estimates/AFE list and
  detail endpoints — relationship-derived fields (`project_code`,
  `well_code`, `afe_code`, `currency_code`) degrade to `null` (the API
  schemas and frontend types are now nullable). This extends the previous
  orphaned-catalogue-item fix from AFE lines to the whole planning chain.

## 2026-08-21 — AFE consolidation, rate basis, and the Sakai shell

Well requirements and the AFE were two names for one document, so they are now
one: **AFE** holds the project, the well, the AFE, and every AFE line on a single
page, and the separate Well Intake module is gone. Lines now say how they are
charged, sections come from configuration rather than free text, and the app
wears the PrimeVue Sakai layout.

### Added

- **Section is configured, not typed.** An AFE line carries `hole_section_id`, a
  foreign key to the hole sections maintained under Master Data, in place of the
  free-text `section_name`. The line grid, the Excel profile
  (`hole_section_code`), and the paste dialog all resolve a section by code or
  name and reject one that is not configured.
- **Rate basis per line.** `afe_lines.rate_basis` records how a line is charged —
  `daily`, `per_service`, `per_section`, `fixed`, `per_unit`, or
  `daily_consumption`. The catalogue item supplies the default (services already
  carried `rate_basis`; mud chemicals and cement additives gained one) and the
  planner may override it for a single line. A basis the item type does not allow
  is refused, and a `per_section` line must name its section.
- **Daily usage for chemicals and additives.** Enter consumption per day and
  planned days and the app computes the total quantity
  (`computed_quantity = daily_consumption × planned_duration_days`). The planner
  may still enter a different quantity, but only with a
  `quantity_override_reason`; an unexplained mismatch is rejected rather than
  silently accepted, and the computed figure stays recorded beside the override.
  Changing usage or planned days recomputes a computed line and leaves an
  explained override alone.
- **Dashboard.** `/dashboard` is the post-login landing page: AFEs in draft and
  submitted, active wells, cost builds, recent AFEs, posted cost states, platform
  health, and the metrics still pending a confirmed policy. Every figure comes
  from a live endpoint; nothing is invented to fill a widget.
- **Sakai layout shell.** A grouped sidebar (Home, Planning, Execution,
  Configuration), a topbar with a light/dark switch, and a theme configurator for
  the preset (Aura/Lara/Nora), primary colour, surface palette, and static or
  overlay menu. The choice is remembered between sessions. Modelled on
  [primefaces/sakai-vue](https://github.com/primefaces/sakai-vue) and re-expressed
  in the project's own CSS, since this app does not use Tailwind.

### Changed

- **Breaking — requirements are AFEs.** Migration `20260821_0017` renames
  `well_requirements` → `afes` and `requirement_items` → `afe_lines`, with
  `cost_estimates.afe_id`, `estimate_items.afe_line_id`, and
  `afe_snapshots.afe_code`, and rebuilds the reporting contract views on the
  renamed tables. Existing `section_name` text is matched to a configured hole
  section by code or name where one exists.
- **Breaking — API.** `/requirements` → `/afes`, `/requirement-items` →
  `/afe-lines`, `/requirements/{id}/items` → `/afes/{id}/lines`, and
  `/estimates/from-requirement` → `/estimates/from-afe`. The standalone baseline
  snapshot read moved from `/afes/{snapshot_id}` to
  `/afe-snapshots/{snapshot_id}` so it no longer collides with the AFE itself.
  The AFE-line Excel profile is version `2.0`.
- **Navigation.** Well Intake and the separate requirement detail page are gone;
  Dashboard and Administration are in the sidebar, and the post-login landing
  route is the Dashboard rather than Master Data.

## 2026-08-20 — Well intake, AFE builder, and catalogue classification

The full workflow is now reachable from the navigation bar instead of being
hidden behind feature flags: enter projects, wells, and requirements on **Well
Intake**, generate the cost build and AFE baseline in **Cost Builder (AFE)**,
and maintain the catalogue on **Master Data**.

### Added

- **Well Intake UI.** Projects, wells (rig, status, spud/completion dates), and
  requirements are created and maintained in the browser. Requirement detail
  pages edit the line-item grid (catalogue item, cost code, quantity, section,
  planned days/depths), then submit the requirement to the Cost Builder.
- **Service rate classification.** Services now carry a `rate_basis`
  (daily rate / per section / per service / fixed rate) on the Services page,
  matching the well rate book's pricing model. Free-text labels such as
  "Fixed rate" are normalised to the stored enum on save and Excel import.
- **Tangible sub categories.** A configurable `item-subcategories` master-data
  page plus a **Sub category** dropdown on the Tangibles page. Sub categories
  are scoped (`applies_to`) and flow through Excel import/export and the API.
- **Rate Revisions export and print.** The rate change log now has the same
  Export (Excel) and Print buttons as every other grid page, with a dedicated
  `/export/rate-revisions` workbook.
- **Navigation.** All modules are enabled: Well Intake, Cost Builder (AFE),
  Master Data, Cost Control, Reports, and Assurance. The post-login landing
  route is now Well Intake.

### Changed

- **Grid data entry.** New rows are always inserted at the top of the grid
  (never the bottom), and grids no longer re-sort alphabetically while you
  type — rows keep their position until you save, then the server re-sorts.
- **Tangible rate revisions.** The row action on Tangible Rates is now a
  clearly labelled **Revise** button next to Edit.
- Dropped the invalid `nitro.maxRequestBodySize` option (no longer supported
  by the locked Nitro version) so `npm run typecheck` is green again.

## 2026-08-20 — Well-scoped rate governance

Rates are renegotiated periodically while twenty rigs drill at once. A revision
must not move a well that is already drilling, and an approved AFE must not be
edited when the field consumes something nobody planned. Three layers now carry
that: master data, a per-well rate book, and an out-of-AFE register. See
[well-scoped rate governance](docs/architecture/well-rate-governance.md) and the
[API reference](docs/api/well-rate-governance.md).

### Added

- **Well rate book.** `well_service_rates` and `well_tangible_rates` hold the
  rates one well will use. Services are typed in per well; tangibles copy the
  master rate in force when the item is picked (`master_unit_rate`,
  `master_price_id`, `master_effective_from`) and may be overridden with a
  reason, which surfaces as `is_overridden` and `variance_to_master`.
  Isolation between rigs is structural: after the copy there is no live link to
  the master rate, so no cut-off date or as-of query can get it wrong.
- **Rate locking.** `POST /wells/{id}/rate-book/lock` freezes the book when the
  AFE baseline is issued. Repricing a locked row returns
  `well_rate_book_locked` and points at the out-of-AFE register; notes and
  contract references stay editable.
- **Well rate change log.** `well_rate_revisions` appends every add, revision,
  lock, and withdrawal with before/after rate snapshots, the reason, and the
  actor. A reason is mandatory for any rate change after a row is created.
- **Out-of-AFE register.** `well_unplanned_items` records services, tangibles,
  and items absent from master data that were consumed outside the approved AFE:
  quantity × rate, `reason_code`, mandatory justification, and a
  `draft → submitted → approved | rejected` workflow. Approving a catalogue item
  adds it to the well rate book already locked, so the rest of the well uses one
  consistent rate. The AFE itself is never touched.
- **Cost exposure.** `GET /wells/{id}/cost-exposure` reports the approved AFE
  total, approved and pending out-of-AFE spend, and the resulting variance.
- **Master rate revisions.** `POST /procurement/item-prices/{id}/revise` closes
  the current rate the day before the new one takes effect and inserts the next
  revision (`revision_number`, `supersedes_id`, `change_reason`). Every change is
  appended to the new `rate_revisions` log, exposed at
  `GET /procurement/rate-revisions` and on the new **Rate Revisions** page. The
  log is backfilled for rates that already existed.
- **Well operating context.** `wells` gained `rig_name`, `status`, `spud_date`,
  `completion_date`, `rates_locked_at`, and `rate_lock_reference`.
- `app/domain/well_costing/rate_lock.py`: the lock, reason, transition, and
  variance rules as pure functions, with unit tests.
- An optional `row-actions` slot on the enterprise grid, used for **Revise rate**.

### Changed

- **Master data holds a rate for tangibles and consumables only.** Master
  service rate cards are retired: the `service_rate_cards` table, its
  `/procurement/service-rates` endpoints, its Excel mapping profile, and the
  Service Rates page are removed, because a service is priced per well.
  Creating a master rate for a service now returns a `422` explaining where the
  rate belongs.
- **Item Prices** is now **Tangible Rates**, showing the revision number and the
  reason for the current revision, with a **Revise** action per row.
- `item_prices.vendor_id` is nullable: a catalogue rate can exist before the
  supplying vendor is fixed.

### Fixed

- `npm ci` in the frontend job: the lockfile was missing two transitive
  `@nuxt/cli` entries (`cac`, `commander`), so a clean install refused to run.

### Migration

`20260820_0015_well_scoped_rate_governance` drops `service_rate_cards`, extends
`item_prices` and `wells`, and creates `rate_revisions`, `well_service_rates`,
`well_tangible_rates`, `well_rate_revisions`, and `well_unplanned_items`. Any
master service rate card is removed by this upgrade; re-enter those rates on the
wells that use them.

## 2026-08-18 — Service-order Excel preview 502

### Fixed

- Excel uploads through the Nuxt `/api/v1` proxy no longer decode the multipart
  body as UTF-8. That corruption made Content-Length no longer match the bytes
  sent to FastAPI, so the API hung or reset and the UI showed
  `[POST] "/api/v1/import/service-orders/preview": 502 Bad Gateway`.
- Nitro's default 1 MB request body limit is raised to 16 MB so typical
  workbooks are not rejected before they reach the import pipeline.
- The workbook reader now drops Excel's padded used range (blank header cells
  and long runs of empty rows) and caps imports at 10,000 data rows, which
  previously could exhaust memory and crash the API worker — another 502.
- Service-order and purchase-order preview now coerce Excel dates, serials, and
  common `DD/MM/YYYY` strings, plus numeric order numbers, before validation.

### Changed

- Proxy timeouts and upstream connection failures return the standard API error
  envelope (`gateway_timeout` / `bad_gateway`) instead of an opaque 502 string.

## 2026-08-17 — Master Data export/print, and landing on enabled pages only

### Added

- **Export** on every Master Data tab, including Service Orders and Purchase
  Orders, which previously had none. The grid now takes an `export-entity` key
  and downloads `GET /export/{entity}` as `{entity}-export.xlsx`; because export
  and import share one mapping profile, an exported workbook re-imports
  unchanged. Service Rates, Item Prices, Currencies, and Item Categories gained
  the button too, so all twelve tabs behave the same.
- **Print** on every Master Data tab. A print-only rendering of the loaded rows
  is emitted as a plain table — no editors, toolbars, filters, or actions column
  — printed A4 landscape with repeating headers. `Ctrl+P` yields the same sheet.
- `frontend/utils/navigation.ts`: one source of truth for which top-level
  modules are enabled, consumed by the navigation bar, the `/` landing route,
  and the post-login redirect.
- `frontend/utils/download.ts`: shared blob-download helper replacing the
  handler that was copy-pasted across pages.
- Unit tests for the navigation model, the sidebar, the grid's export and print
  behaviour, and the login redirect.

### Fixed

- The application no longer opens the **Cost Library**, which is not an enabled
  page. Signing in and visiting `/` now land on the first enabled module (Master
  Data). Previously both paths were hard-coded to `/cost-library/services`, and
  `/` rendered a foundation dashboard advertising unreleased modules, so the app
  always started somewhere the user could not act.

### Changed

- Export button labels use the Excel icon and report success or a readable
  failure message in the grid's existing feedback area.
- The navigation bar renders only enabled modules rather than filtering a list
  that also carried disabled entries; releasing a module is now a one-line flag
  change that updates the nav, landing route, and redirect together.
- Per-page `exportWorkbook` handlers in Vendors, Units, and `CatalogueGrid` were
  removed in favour of the shared grid implementation.

## 2026-08-16 — Supabase Auth sign-in

### Added

- Optional Supabase Auth sign-in: when `SUPABASE_URL` plus an API key
  (`SUPABASE_ANON_KEY`, or `SUPABASE_SERVICE_ROLE_KEY` as a fallback) are set in
  `backend/.env`, users created in Supabase Authentication can sign in through the
  normal login page with their Supabase email and password.
- `SupabaseAuthClient` integration that validates credentials against Supabase's
  GoTrue password grant (`/auth/v1/token?grant_type=password`) without ever
  storing the user's password in the application database.
- Login fallback order: local password hash first (existing provisioned users and
  the bootstrap administrator keep working), then Supabase Auth. A Supabase
  identity is mirrored into `users` with `auth_provider='supabase'` and a NULL
  password hash on first sign-in.
- Migration `20260816_0013_add_supabase_authentication` — makes `users.hashed_password`
  nullable and adds the `users.auth_provider` column (SQLite and PostgreSQL paths).

### Changed

- `users.hashed_password` is now nullable; `users.auth_provider` defaults to `local`.
- The login page reports a dedicated message when Supabase Auth is unreachable
  (`auth_service_unavailable`).

## 2026-08-16 — Termux deploy: OpenSSL CLI package fix

### Fixed

- First-time setup no longer stops at step [5/7] with `openssl: command not
  found`: Termux installers now request `openssl-tool`, which contains the CLI,
  instead of the library-only `openssl` package. JWT key generation also falls
  back to Node's cryptographically secure random-byte API.

## 2026-08-16 — Termux deploy: backend install on older-glibc containers (argon2 → bcrypt)

### Fixed

- `pip install` failing in step [3/7] with `no matching distributions available
  for your environment: argon2-cffi-bindings` on phones whose long-lived Debian
  container has glibc < 2.26: `argon2-cffi-bindings` was the only dependency
  whose aarch64 wheels require `manylinux_2_26`/`2_28`. Password hashing now
  uses **bcrypt**, whose wheels cover `manylinux2014` (glibc 2.17) aarch64 like
  every other pinned native wheel, so the wheels-only install resolves on
  decade-old containers and modern ones alike.
- proot-distro 5.x compatibility: the deploy no longer attempts a fresh
  container install when one already exists — detection now accepts both the
  legacy `installed-rootfs/<name>` and the 5.x `containers/<name>/rootfs`
  layouts (previously the first deploy aborted with "container 'debian'
  already exists").
- A failed backend install now prints the container's architecture, glibc
  version, and the pip-supported `manylinux` wheel tags, so wheel-platform
  mismatches are diagnosable from the log alone.

### Changed

- Password hashing: bcrypt is the guaranteed baseline on every deployment.
  Installs with the new optional `argon2` extra (`pip install .[argon2]`; wired
  into `scripts/render_build.sh` for cloud) keep Argon2id as the primary
  hasher, so existing Argon2-hashed accounts keep working there; bcrypt hashes
  remain verifiable in every environment, including Termux. A stored hash whose
  scheme is unavailable locally now yields a normal "invalid credentials" 401
  instead of a 500.

## 2026-08-16 — Termux deployment: Debian-prooted backend (pydantic-core fix)

### Fixed

- Termux setup hanging while building `pydantic-core` (and later `watchfiles`) from
  Rust/C source: the backend Python environment now runs inside a `proot-distro`
  Debian container where every dependency in `backend/pyproject.toml` installs as a
  prebuilt `manylinux_aarch64` wheel — nothing compiles on the phone.
- Broken `deploy.sh` venv mismatch: setup created `backend/.venv-debian` while
  `update_code()` / `run_migrations()` / `start_servers()` (and `start.sh`,
  `migrate.sh`, `update.sh`) activated `backend/.venv`, so deploys crashed after
  setup. All scripts now share `termux/lib-debian-backend.sh` and use one
  Debian-managed venv at `backend/.venv` (stale `.venv` / `.venv-debian`
  directories are detected via a marker file and recreated automatically).
- Corrupted `DATABASE_URL` when a pasted Supabase password contained `&`, `|`, or
  `\` (unescaped `sed` replacement during the deploy prompt).
- `deploy.sh` self-heals when the setup marker exists but the Debian-managed venv
  is missing; the Python version gate (`>=3.12,<3.14`) falls back to a uv-managed
  CPython 3.12 if Debian's system Python ever leaves the supported window.
- Backend startup now waits for `/api/v1/live` and reports a log hint on timeout;
  `start.sh` takes a Termux wake lock; Nuxt production serving sources
  `frontend/.env` (HOST/PORT/proxy settings) and falls back to Termux's `esbuild`
  package when the bundled esbuild binary won't run.

### Added

- `termux/backend-exec.sh` — run any backend command inside the Debian container
  (Alembic, pytest, seed scripts) with `SEED_USER_*`/`DATABASE_URL` forwarding.

## AFE reference data

### Added

- Vendor classification (`third_party` / `inhouse`) with contact, email, phone, and country.
- `item_categories` for catalogue classification (bits, casings, shoes and collars, wellheads, and consumable groups), scoped by `applies_to`.
- `mud_chemical` and `cement_additive` catalogue types with unit of measure and unique material numbers.
- `service_orders` and `purchase_orders` registers linked to vendors and currencies.
- `service_rate_cards` holding operating, standby, mobilisation, and demobilisation rates as columns, with optional hole-section scoping and effective dating.
- `item_prices` for effective-dated tangible and consumable prices linked to purchase orders.
- Ten Master Data pages built on a reusable enterprise grid with server-side pagination, entity-specific filters, inline Excel-style editing, clipboard paste, and per-row edit/delete actions.
- Excel mapping profiles, templates, imports, and exports for the new entities.
- Migration `20260814_0012_add_procurement_and_consumable_master_data`.

### Changed

- Master-data list endpoints accept typed filter parameters; catalogue search now also matches material number, specification, and manufacturer.
- `DELETE` endpoints accept `?hard=true` and return 409 when a record is still referenced.
- The `vendors` Excel mapping profile is now version 1.1 (additional columns).

## [Unreleased]

- Draft enterprise configuration publication and numeric rules require separate approval.
- Production activation remains blocked pending security and operating policies.

## 2026-08-13 — Enterprise Configuration Foundation completed

### Added

- Configurable typed enterprise hierarchy and explicit parent-child rules.
- Versioned cost breakdown structures, rate books, estimate templates, and reporting mappings.
- Bootstrap System Administrator write boundary and Enterprise Setup UI.
- Draft-only configuration APIs with audit actors/timestamps; no guessed hierarchy or publication.

### Validation

- PostgreSQL migration round trip passed through `20260813_0011`.
- 54 backend tests passed with 81.21% coverage; Ruff and strict Pyright passed.
- Frontend typecheck, ESLint, 13 Vitest tests, production build, npm audit, and 3 Playwright tests passed.

## 2026-08-13 — Phase 11 Framework Assurance completed

### Added

- Authenticated cross-module assurance status and UI.
- Live checks for blocked financial outputs, workflow/AFE/posting immutability, and actor attribution.
- 10,000-row bulk assurance and optimized master-reference preloading.
- Final security, scale, API, and acceptance-blocker documentation.

### Validation

- 53 backend tests passed with 80.52% coverage; Ruff and strict Pyright passed.
- Frontend typecheck, ESLint, 13 Vitest tests, production build, 3 Playwright tests, and npm audit passed.
- PostgreSQL 16.14 staged 10,000 rows in 4.886 seconds with zero errors.
- Reporting PUBLIC privileges/grants were absent and workspace secret scan was clean.

### Blocked

- Numeric workbook reconciliation and formula acceptance.
- Production role/security matrix and active workflow/AFE/posting policies.
- Production deployment, operations, recovery, monitoring, and reporting identity approval.

## 2026-08-13 — Phase 10 Reporting Contract v1 completed

### Added

- PostgreSQL `reporting` schema with versioned transaction fact, six dimensions, policy metadata, and contract metadata views.
- Contract discovery API, in-app contract panel, Power BI mapping guide, and commented grant template.
- Transactional schema privacy and `direct_grants_status=not_applied` guardrails.

### Validation

- PostgreSQL 16.14 migration round trip passed through `20260813_0010`; nine v1 views queried successfully.
- 51 backend tests passed with 80.23% coverage; Ruff and strict Pyright passed.
- Frontend typecheck, ESLint, 12 Vitest tests, production build, 3 Playwright tests, and npm audit passed.

### Deferred

- Production reporting principal/grants, gateway, refresh SLA, row-level security, and numeric KPI views.

## 2026-08-13 — Phase 9 Shared-Dimension Reporting framework completed

### Added

- Full shared-dimension report API, dashboard filters/cards, source drill-through, pending chart state, and Excel export.
- Pure pending financial-metric boundary and actor/file-hash export audit.

### Validation

- PostgreSQL 16.14 migration round trip passed through `20260813_0009`.
- 51 backend tests passed with 80.15% coverage; Ruff and strict Pyright passed.
- Frontend typecheck, ESLint, 12 Vitest tests, production build, 3 Playwright tests, and npm audit passed.

### Deferred

- Reporting currency, overlap, variance, forecast/EAC, rounding, cut-off, and zero-budget metrics.
- Stable Power BI/SQL views remain Phase 10.

## 2026-08-13 — Phase 8 Cost Control framework completed

### Added

- Separate typed field-estimate, commitment, accrual, actual, and forecast records.
- Bulk manual/paste staging, Excel preview/template, row errors, history, and blocked post auditing.
- Immutable future transaction/source-document lineage and append-only reversal/adjustment references.
- Cost Control UI and typed `cost_state_policy_pending` boundary.

### Validation

- PostgreSQL 16.14 migration round trip passed through `20260813_0008`.
- 49 backend tests passed with 79.79% coverage; Ruff and strict Pyright passed.
- Frontend typecheck, ESLint, 11 Vitest tests, production build, 3 Playwright tests, and npm audit passed.
- PostgreSQL confirmed one blocked forecast batch/attempt and zero posted transactions.

### Deferred

- Recognition, allocation, matching, FX/tax/sign, reconciliation, forecast/EAC, and reversal amount/period rules.

## 2026-08-13 — Phase 7 Immutable AFE Baseline framework completed

### Added

- Pure typed baseline AFE input/output contracts and mandatory discovery boundary.
- Immutable AFE header/line persistence framework with calculation provenance, copied dimensions, totals, source snapshots, timestamps, and actors.
- Audited explicit snapshot attempts with workflow/calculation eligibility evidence.
- AFE status/create/read APIs and typed `afe_policy_pending` response.
- Cost Builder AFE baseline panel, policy register, explicit request, blocked message, and attempt history.
- Backend AFE domain/audit tests, frontend pending-policy test, PostgreSQL browser regression, and Phase 7 documentation.

### Validation

- PostgreSQL 16.14 full migration round trip passed through `20260813_0007`.
- 46 backend tests passed with 78.63% coverage; Ruff and strict Pyright passed.
- Frontend strict typecheck, ESLint, 10 Vitest tests, production build, 3 Playwright tests, and dependency audit passed.
- PostgreSQL confirmed zero AFE headers/lines, one blocked actor-attributed attempt, and unchanged/null estimate financial state.

### Deferred

- Active AFE eligibility, numbering, issuance, and accounting-handoff policy.
- Revisions, supplements, void/correction behavior, attachments, and authorization rules.

## 2026-08-13 — Phase 6 Review & Approval Workflow framework completed

### Added

- Pure typed state-machine contracts and deterministic structural transition evaluator.
- Versioned workflow profiles, states, transition definitions, role mappings, estimate workflow instances, transition attempts, and immutable review comments.
- Estimate workflow/profile/comment APIs with typed `workflow_profile_pending` errors.
- Fail-closed transition auditing under policy `pending-estimate-review`; no profile, role, state, or transition defaults were seeded.
- Cost Builder workflow status, pending-policy register, transition trace, and review-note panel.
- Backend workflow/purity/audit tests, frontend pending-policy test, and PostgreSQL full-stack regression.
- Phase 6 API, database, architecture, pending-policy, and completion documentation.

### Validation

- PostgreSQL 16.14 full migration round trip passed through `20260813_0006`.
- 44 backend tests passed with 77.51% coverage; Ruff and strict Pyright passed.
- Frontend strict typecheck, ESLint, 9 Vitest tests, production build, 3 Playwright tests, and dependency audit passed.
- PostgreSQL E2E verification confirmed a blocked actor-attributed transition attempt, no workflow instance, unchanged estimate status, null financial values, and one actor-attributed review note.

### Deferred

- Active estimate states, transitions, approval/rejection behavior, and role mappings.
- Workflow administration/publication UI and APIs until configuration permissions are approved.
- Calculation prerequisites, approval thresholds, delegation, separation of duties, and in-flight profile migration policy.

## 2026-08-13 — Phase 5 Costing Engine framework completed

### Added

- Pure typed full-chain input/output contracts and a mandatory discovery `NotImplementedError` calculation boundary.
- Audited calculation runs with engine/rule-set versions, input/output snapshots, status, timestamps, and actor fields.
- Nullable version totals and a future transactional result-persistence boundary.
- Calculate/results APIs with typed `business_rule_pending` errors and explicit pending-rule details.
- Cost Builder recalculation action, status, nullable total cards, category-chart empty state, and pending-rule trace.
- Backend framework/audit tests, frontend empty-state test, and full-stack blocked-calculation regression.
- Phase 5 API, database, architecture, pending-rule, and completion documentation.

### Validation

- PostgreSQL 16.14 full migration round trip passed through `20260812_0005`.
- 40 backend tests passed with 76.68% coverage; Ruff and strict Pyright passed.
- Frontend strict typecheck, ESLint, 8 Vitest tests, production build, 3 Playwright tests, and dependency audit passed.
- PostgreSQL E2E verification confirmed blocked audit input, null output, and zero populated line/version financial values.

### Deferred

- Every numeric strategy in the full calculation chain and all numeric acceptance tests.
- Source-workbook scenario reproduction, because original workbooks and certified expected outputs remain unavailable.

## 2026-08-12 — Phase 4 Bulk Cost Build completed

### Added

- Versioned cost estimates, line-item skeletons, manual vendor/rate assignment, assumptions and version duplication.
- Cost Builder UI with bulk grid, vendor/rate fill, quantity edits, line duplication and version selection.
- Estimate-line Excel templates, preview/commit and export.
- Explicit pending-calculation fields and automatic-rate placeholder.

### Validation

- PostgreSQL 16 full migration round trip passed.
- 38 backend tests passed with 75.96% coverage.
- Ruff, strict Pyright, frontend lint/typecheck, 7 unit tests, production build, 3 Playwright tests and dependency audit passed.

### Deferred

- Automatic rate/vendor selection and every financial calculation.
- Confirmed scenario cost builds remain blocked by missing Phase 0 source package.

## 2026-08-12 — Phase 3 Requirement Intake completed

### Added

- Auditable projects, wells, well requirements, and requirement items.
- Bulk CRUD APIs, project/well/status filters, active-reference validation, and Draft/Submitted workflow.
- Requirement line quantities/units, sections, planned days, and optional unit-aware depth ranges sourced from discovery concepts.
- Requirement-item Excel mapping profile, template, preview, commit, export, and row-level errors.
- Project → well → requirement frontend workflow and bulk requirement grid with TSV paste, duplicate, import/export, and submission.
- PostgreSQL-backed full-stack Playwright requirement journey.

### Validation

- PostgreSQL 16 full migration round trip passed.
- 34 backend tests passed with 75.01% coverage.
- Ruff and strict Pyright passed.
- Frontend lint, strict typecheck, 7 unit tests, production build, 3 Playwright tests, and dependency audit passed.

### Deferred

- Requirement revision/locking and any statuses beyond Draft/Submitted.
- Certified source-workbook mappings and approved Phase 0 regression scenarios.
- Estimate generation, rate matching, assumptions, and every cost calculation.

## 2026-08-12 — Phase 2 Cost Library and Excel Import completed

### Added

- Auditable units, currencies, cost categories, cost codes, vendors, catalogue items, services, tangibles, materials, equipment, rates, import batches, and import errors.
- Generic typed repositories/services plus named entity boundaries.
- CRUD, pagination, filtering, sorting, deactivation, bulk validation, bulk create, and bulk update APIs.
- Effective-dated rate API linked to item, vendor, currency, and unit.
- Pandas/OpenPyXL/xlrd Excel reader, versioned mapper, row validator, pipeline orchestrator, transactional importer, exporter, and blank templates.
- Excel preview/commit, template, export, history, and error-detail endpoints.
- Cost Library UI with spreadsheet-style grid editing, add rows, TSV paste, multi-select, duplicate, bulk edit, deactivation, import, and export.
- Rate grid with catalogue/vendor/currency/unit selection.
- Excel import wizard with mapping override, validation summary, row errors, preview, and commit.
- Import history page and minimal login flow.
- Synthetic valid, invalid, and duplicate Excel regression fixtures.
- Full-stack Playwright Excel import test and PostgreSQL CI job.

### Validation

- PostgreSQL 16 migration downgrade/upgrade passed.
- 25 backend tests passed with 76.31% coverage.
- Ruff and strict Pyright passed.
- Frontend lint, strict typecheck, 7 unit tests, production build, and 2 Playwright tests passed.
- Frontend dependency audit reported zero vulnerabilities.

### Deferred

- Actual workbook-specific mapping profiles and approved Phase 0 regression data.
- Rate overlap/precedence, vendor selection, currency conversion, and every costing formula.
- Final master-data delete/restore policy and organization-specific attributes.

## 2026-08-12 — Phase 1 foundation completed

### Added

- Nuxt 3, strict TypeScript, PrimeVue Aura, Pinia, and ECharts frontend foundation.
- Responsive dashboard shell, static phase navigation, reusable state components, and preconfigured data-table wrapper.
- Centralized typed API client, API proxy, health/auth composables, and auth store scaffolding.
- FastAPI application with Pydantic settings, SQLAlchemy sessions/base mixins, Alembic, structured logging, and normalized global exceptions.
- PostgreSQL users, roles, and user-role migration with verified upgrade/downgrade round trip.
- Argon2 password hashing, JWT access tokens, login/current-user endpoints, and authentication dependency.
- Pure Python costing placeholders and framework-isolation test.
- Excel reader/mapper/validator/importer/exporter/template interfaces.
- Backend unit/integration tests, frontend Vitest component/composable tests, and Playwright smoke test.
- GitHub Actions backend/frontend jobs with PostgreSQL 16 service.
- Windows/no-Docker setup, architecture, database, API, Excel, testing, ADR, business-rule, and Phase 1 completion documentation.

### Validation

- PostgreSQL 16.14 migration round trip passed.
- 18 backend tests passed with 88.16% coverage.
- Ruff and strict Pyright passed.
- Frontend lint, strict typecheck, 4 unit tests, production build, and Playwright smoke test passed.
- Frontend dependency audit reported zero vulnerabilities.

### Deferred

- All business data models and calculations, real Excel processing, permissions hardening, AFE, actuals, forecasting, dashboards, and Power BI integration.
- Phase 0 workbook certification inputs remain pending and no rule has been guessed.

## 2026-08-12 — Phase 0 industry-reference baseline

- Added a public-source study of established well-costing, well-operations, AFE, actual-cost, and reporting workflows.
- Adopted a configurable requirement-to-reporting reference workflow while retaining workbook/business confirmation as the authority for formulas.
- Explicitly excluded upstream well-design calculations.
- Recorded that the original workbook package and certified regression scenarios remain incomplete.
