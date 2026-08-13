# Industry-Reference Well Costing Application Workflow

**Project:** Drilling Costing  
**Status:** Phase 0 industry-reference baseline — adopted for subsequent design, subject to confirmed business rules  
**Date:** 2026-08-12  
**Purpose:** Establish a globally recognizable, configurable well-costing workflow without inventing company-specific business rules.

## 1. Decision

The application should use the common workflow patterns found across established well-cost, well-operations, AFE, and capital-control products, but it should **not copy a vendor product** and should **not use public industry examples as authority for company-specific formulas**.

The recommended design is:

> **A stable financial core surrounded by versioned configuration.**

The stable core protects auditability, calculation reproducibility, approvals, and historical snapshots. Configuration lets authorized administrators change cost structures, templates, mappings, reference lists, workflow labels, roles, and reporting views without restructuring the application.

The original project boundaries remain unchanged:

- Well-planning systems supply requirements to this application.
- This application does not calculate trajectory, BHA, hydraulics, casing design, cement design, drilling simulation, formation evaluation, or rig selection.
- Excel files and confirmed business input remain the only authority for actual rate, contingency, escalation, currency, vendor-selection, AFE, actual-cost, and forecast rules.
- Industry research can define the **shape of the workflow**, not unconfirmed numeric behavior.

## 2. Research scope and limitations

This study reviewed publicly available product descriptions and documentation for representative categories:

- Well-cost estimation and risk-based costing
- Well operations and daily cost capture
- AFE creation, review, approval, and control
- Field estimates, accruals, commitments, accounting actuals, and forecasting
- Industry data and cost-classification standards
- Trading-partner price sheet, field ticket, and invoice exchange

Publicly visible workflows were considered from Halliburton Well Cost/OpenWells, Peloton WellView, Quorum Execute/Well Operations, W Energy AFE, Resource Energy Solutions, IFS Energy & Resources, PIDX, PPDM/Energistics references, and ISO 19008.

This is not a proprietary schema review, a feature-by-feature procurement comparison, or proof that every operator uses the same process. Public sources consistently show a recognizable operating pattern, while classifications, approval levels, formulas, and reporting obligations remain organization-specific.

## 3. What established applications commonly do

### 3.1 Halliburton Well Cost and OpenWells

Halliburton describes Well Cost as supporting both high-level budgeting and detailed AFE work, deterministic or probabilistic estimates, organizational standardization, historical data, and transfer of cost/activity data to OpenWells [3](https://www.halliburton.com/en/software/decisionspace-365-enterprise/decisionspace-365-well-construction/well-construction-suite/well-cost-software).

OpenWells publicly documents a strong estimate-to-actual relationship:

- A Cost Estimate and AFE report records planned event costs for later comparison with actuals [2](https://esd.halliburton.com/support/LSM/Drilling/EDMEDTSuite/OpenWells/5000/5000_1/Help/Reports/Cost_Estimate_AFE/Cost_Est_&_AFE_Report.htm).
- Daily actual costs are associated with an AFE and may be edited or imported across multiple days [1](https://esd.halliburton.com/support/LSM/Drilling/EDMEDTSuite/OpenWells/5000/5000_1/Help/Interactive_Well_Site/Daily_Operations_Data/cost_data.htm).
- The definition of a cost line can be configured from company dimensions; the documented default uses cost class, code, and subcode rather than assuming one universal breakdown [1](https://esd.halliburton.com/support/LSM/Drilling/EDMEDTSuite/OpenWells/5000/5000_1/Help/Interactive_Well_Site/Daily_Operations_Data/cost_data.htm).
- Supplemental AFEs preserve additions that were not anticipated in the initial estimate [8](https://esd.halliburton.com/support/LSM/Drilling/EDMEDTSuite/OpenWells/5000/5000_1/Help/Reports/Cost_Estimate_AFE/Supplemental_-_AFE.htm).

**Pattern to adopt:** planned and actual costs use compatible coding dimensions; approved baselines are not silently overwritten; company-specific cost-line definitions remain configurable.

**Pattern not to copy yet:** the published OpenWells contingency and rental formulas are examples of that product's behavior, not confirmed rules for this project.

### 3.2 Peloton WellView

Peloton presents WellView as a shared well lifecycle record with configurable workflows and views, source validation, automatic version control, historical reporting, links between operational events and costs, and export/integration capabilities [3](https://www.peloton.com/products/well-data-lifecycle/wellview).

**Pattern to adopt:** one governed record connects well context, operational events, cost entries, versions, validations, and reporting. Templates and views should adapt by role or asset without duplicating core data.

**Boundary:** this costing application may hold the minimum project/well/event context needed for costing, but it will not attempt to reproduce WellView's broader well lifecycle or digital-well functionality.

### 3.3 Quorum Execute AFE and Well Operations

Quorum's public AFE workflow connects estimate records, approvals, field costs, accounting actuals, accruals, capital budgets, and remaining forecasts. It emphasizes configurability, auditable approval records, integration with accounting/well systems, and a single view of spending from multiple sources [3](https://www.quorumsoftware.com/solutions/planning-economics-reserves/execute/afe/).

Quorum Well Operations describes daily costs, time and activity codes aligned to well/job AFE budgets, field estimates allocated to AFEs/projects/vendors, and actual-versus-AFE visibility [4](https://www.quorumsoftware.com/solutions/upstream-on-demand/well-operations/).

**Pattern to adopt:** retain budget, field estimate/accrual, accounting actual, and forecast as separate cost states that reconcile through shared codes and references.

### 3.4 Configurable AFE products

W Energy publicly emphasizes configurable AFE templates, cost-estimate rules, approval rules, roles, field estimates, actuals, budgets, and parent-child AFEs [1](https://wenergysoftware.com/solutions/afe-authorization-for-expenditure/).

Resource Energy Solutions describes line-item budgets based on built-in or customized templates, accounting-system integration, comparison of budget to field estimate to actual, electronic routing, approvals, and audit trails [5](https://resourceenergysolutions.com/afe-manager-software/).

IFS describes AFE creation/approval, visibility into capital spend, and real-time comparison of field estimates and actual costs against AFE budgets [1](https://www.ifs.com/en/insights/assets/energy-and-resources-afe).

**Pattern to adopt:** make organizational configuration a first-class, versioned feature rather than scattering company-specific values through code.

### 3.5 Standards and integration references

PIDX standardizes trading-partner exchanges and publishes compatible upstream schemas for price sheets, purchase orders, field tickets, invoices, invoice responses, receipts, and related documents [2](https://pidx.org/standards/).

PPDM material identifies upstream concepts such as projects, business associates, units of measure, rate schedules, AFEs, budgets, and financial-accounting references across the well lifecycle [1](https://dl.ppdm.org/dl/1882). Energistics documents WITSML as covering wells, wellbores, logs, mud logs, and related equipment [3](https://docs.energistics.org/CTA/CTA_TOPICS/CTA-000-002-0-C-sv2100.html).

ISO 19008:2026 defines an oil-and-gas standard cost coding system for estimation, benchmarking, monitoring, quantities, work hours, cost data exchange, and cost-system implementation. It also states that the standard is a basis for organization-specific accounting, AFE, billing, and project breakdown structures rather than a substitute for them: https://www.iso.org/standard/88670.html.

**Patterns to adopt:**

- Keep external identifiers and mapping profiles so standards-based integration remains possible.
- Treat WITSML as an optional source of well/operational context, not as the application's financial data model.
- Treat PIDX as a future adapter boundary for vendor price sheets, field tickets, and invoices.
- Evaluate ISO 19008:2026 as a mapping/reference structure during master-data discovery; do not replace the company's cost codes without approval.

## 4. Recommended end-to-end workflow

```text
UPSTREAM WELL-PLANNING SYSTEMS
        |
        | approved planning requirements only
        v
1. Requirement Intake
        v
2. Cost Library / Rate Books / Templates
        v
3. Bulk Cost Build
        v
4. Validate + Calculate Estimate
        v
5. Review + Compare + Revise
        v
6. Approved Estimate
        v
7. AFE / Budget Snapshot
        v
8. Field Cost Estimate + Commitments + Accruals
        v
9. Accounting Actuals / Invoices
        v
10. Forecast / Estimate at Completion
        v
11. Variance Review + Close-out
        v
12. Dashboards / Historical Benchmarks / Power BI
```

### 4.1 Workflow stages

| Stage | Purpose | Primary controlled record | Bulk-first interaction |
|---|---|---|---|
| Requirement intake | Receive costing requirements without re-performing engineering design | Requirement version and requirement lines | Paste grid, Excel import, bulk validation |
| Cost library | Maintain reusable items, vendors, units, currencies, cost codes, and effective-dated rates | Published master-data/rate versions | Grid edit, templates, bulk import/export |
| Bulk cost build | Convert requirements into a priced cost structure | Estimate version and estimate lines | Generate from requirement, copy, fill-down, paste, group edit |
| Calculation | Apply only confirmed quantity/rate/contingency/escalation/total rules | Calculation run and immutable input/output snapshot | Recalculate selected or full estimate server-side |
| Review/revision | Explain changes and compare versions | Review record, comments, version diff | Filter changed lines, bulk comments/actions where appropriate |
| AFE/budget | Authorize and freeze the approved financial baseline | AFE version/snapshot | Generate from approved estimate; controlled revision/supplement |
| Field cost control | Capture latest field-estimated liability before invoices are booked | Field estimate, commitment, accrual, or ticket batch | Daily/multi-day grid and imports |
| Actuals | Import booked costs from accounting or approved invoices | Actual-cost transaction/import batch | Mapping, validation, commit, reversal—not destructive editing |
| Forecast | Estimate remaining cost and completion outcome | Forecast version | Bulk category/well adjustments with reason codes |
| Reporting | Compare approved, committed, estimated, actual, and forecast states | Read model/reporting views | Filters, drill-down, exports, Power BI |
| Close-out | Reconcile final costs and retain lessons for future estimates | Closed cost package and benchmark record | Exceptions grid and reconciliation workflow |

## 5. Recommended information structure

### 5.1 Context hierarchy

The application should support the following conceptual hierarchy without implementing upstream engineering calculations:

```text
Portfolio / Asset
  -> Project / Campaign
      -> Well
          -> Job or Costing Event
              -> Phase / Section / Activity reference
                  -> Requirement
                  -> Estimate Version
                  -> AFE Version
                  -> Cost Transactions
```

`Phase`, `section`, and `activity` are costing dimensions supplied by planning/operations or selected from approved reference lists. Their presence does not authorize this application to calculate a well design.

### 5.2 Shared line-item dimensions

A planned, approved, field-estimated, committed, actual, or forecast cost should be reconcilable through a compatible set of dimensions:

- Project, well, and job/event
- Requirement and source line
- Estimate/AFE identifier and version
- Cost category, cost code, and optional subcode
- Cost nature: service, tangible, material/consumable, or equipment
- Item/catalogue code and description
- Vendor
- Phase, section, activity, and reporting date where applicable
- Quantity and unit of measure
- Rate/price reference and rate-book version
- Transaction currency, base/reporting currency, and exchange-rate reference
- Source document: import, quotation, contract, purchase order, field ticket, invoice, journal, or manual adjustment
- Cost state and transaction status
- Audit actor, timestamp, and change/reversal reason

The exact mandatory dimensions must come from discovery and business confirmation. Optional dimensions should not be hard-coded into every workflow.

### 5.3 Cost states must remain separate

```text
Estimate         = current working cost model
Approved Estimate= accepted estimate version
AFE Budget       = authorized snapshot
Field Estimate   = best field view of incurred/not-yet-booked cost
Commitment       = contracted or ordered obligation
Accrual          = recognized estimate pending accounting actual
Actual           = booked financial transaction
Forecast         = actual/commitment plus approved remaining-cost methodology
```

These are related views of cost, not interchangeable columns. Importing an actual must not overwrite the AFE. Publishing a forecast must not mutate historical forecast versions. Reversals and corrections should retain lineage to the original transaction.

## 6. Configuration model for future modification

### 6.1 Safe for authorized administrators to configure

Subject to role permissions and audit logging, the future Administration area should support:

1. **Reference lists** — units, currencies, vendors, cost categories, cost codes/subcodes, phases, sections, activities, and reason codes.
2. **Cost breakdown structures** — named/versioned hierarchies and mappings to accounting or reporting codes.
3. **Item classifications** — service, tangible, material, and equipment catalogues plus organization-specific subtypes.
4. **Rate books** — vendor/item/unit/currency/date-specific rates, commercial references, and lifecycle statuses.
5. **Estimate templates** — reusable line groups, default dimensions, required columns, and applicability criteria.
6. **Excel mapping profiles** — source headers, target fields, transformations from an approved safe library, aliases, and validation profiles.
7. **Workflow profiles** — display labels, permitted transitions, role assignments, required checks, and applicability by project/AFE type.
8. **Approval matrices** — approver roles, ordering, thresholds, delegation, and escalation parameters after business confirmation.
9. **Custom fields** — constrained typed fields for non-core metadata, with validation and reporting visibility.
10. **Dashboard/report definitions** — approved dimensions, filters, display labels, and saved views.

### 6.2 Must remain controlled code plus tests

The following must not become unreviewed spreadsheet-like expressions or arbitrary administrator scripts:

- Quantity resolution algorithms
- Automatic rate-selection precedence
- Currency conversion behavior
- Contingency and escalation formulas
- Tax or tangible/intangible classification algorithms
- AFE authorization and supplemental-approval logic
- Actual-cost allocation rules
- Forecast/EAC formulas
- Financial total and rounding rules
- Access-control enforcement
- Audit and snapshot integrity

A change to these rules requires a documented business-rule source, a versioned domain implementation, regression tests, review, and approval.

### 6.3 Configuration lifecycle

Every material configuration should follow:

```text
Draft -> Validated -> Published -> Retired
```

Each published version should have:

- Stable identifier and version number
- Effective-from/effective-to dates where relevant
- Owner and approval metadata
- Source or rationale
- Created/updated audit fields
- Immutable references from estimates, calculations, AFEs, and imports that used it

Editing a published configuration should create a new version. It should never silently recalculate or reinterpret historical financial records.

### 6.4 Avoid an unrestricted “build anything” data model

Future flexibility should use a hybrid approach:

- Stable relational fields for financial identities and high-value reporting dimensions
- Versioned configuration for organization-specific structures
- Typed custom fields only for genuinely variable metadata
- Mapping layers for Excel, ERP, PIDX, WITSML, and Power BI

A fully generic entity-attribute-value model would make validation, type safety, reporting, and financial audit more difficult. Core financial data should remain explicit and strongly typed.

## 7. Candidate workflow states

These are **industry-reference defaults for later confirmation**, not approved business rules.

| Record | Candidate states |
|---|---|
| Requirement | Draft → Submitted → Locked → Superseded |
| Estimate version | Draft → Validated → Calculated → In Review → Approved/Rejected → Superseded |
| AFE version | Draft → In Review → Approved → Issued → Closed/Superseded |
| Import batch | Uploaded → Mapped → Validated → Committed/Rejected → Reversed |
| Forecast version | Draft → Reviewed → Published → Superseded |

The state-machine service should enforce transitions. Configuration may enable an approved subset and map roles to transitions, but configuration must not bypass immutable snapshots, audit requirements, or authorization checks.

## 8. Bulk-first user experience

The common industry workflow can be retained without recreating Excel's weaknesses:

1. Open an estimate, requirement, rate book, or actual-cost batch as a spreadsheet-style grid.
2. Paste TSV data from Excel or insert many blank rows.
3. Apply fill-down, multi-row edit, duplicate group, mapping, and bulk assignment.
4. Validate all rows without committing.
5. Display cell/row errors with codes and remediation guidance.
6. Commit valid data in one transaction; do not partially commit an invalid financial batch unless a future approved rule explicitly permits it.
7. Keep import batches, source files, mappings, user, timestamp, and error history.
8. Export using the same versioned templates for deterministic round trips.

The frontend may calculate visual conveniences such as selected-row counts, but all financial calculations and validation decisions remain server-side.

## 9. Costing-engine extensibility

The pure Python domain layer should eventually support a registry of explicitly implemented and tested cost-basis strategies. Candidate strategy names may include:

- Quantity × unit rate
- Duration × daily/hourly rate
- Lump sum
- Mobilization/demobilization
- Rental run/standby basis
- Consumption basis
- Percentage-based adjustment
- Tiered/volume rate
- Escalated or effective-dated rate

This list identifies possible extension points only. Each strategy must remain `NotImplementedError` until its formula and precedence are confirmed from Excel/business-rule discovery.

Each completed calculation should record:

- Engine version
- Rule/configuration versions
- Input snapshot/hash
- Calculation timestamp and actor
- Line-level explanation or trace
- Warnings and unresolved inputs
- Output totals and currency basis

Do not allow executable Python, SQL, JavaScript, or unrestricted formula strings to be stored as administrator configuration.

## 10. Integration boundaries

### Inbound

- Well-planning requirement handoff through Excel initially and REST later
- Master/reference data from controlled Excel imports
- Vendor rates/price sheets through Excel; PIDX adapter may be added later
- Field tickets, purchase orders, commitments, and invoices in later phases
- Accounting actuals through staged, validated imports or an ERP adapter
- Exchange rates from an approved source only after ownership and rules are confirmed

### Outbound

- Excel estimates, AFE packages, and reconciliation extracts
- REST APIs for approved consumers
- Stable PostgreSQL reporting views for Power BI
- Audit and calculation trace exports

### Optional standards alignment

- **PIDX:** future price sheet, field ticket, purchase order, and invoice interfaces
- **WITSML:** optional well/job/activity context only
- **PPDM:** terminology and identifier/reference review, not wholesale adoption of its large model
- **ISO 19008:2026:** cost-code mapping/benchmark reference, subject to licensing and business approval

## 11. Refinements to the existing phase roadmap

The fixed technology stack, modular-monolith architecture, and phase gates do not need to change. The following refinements make future modification easier:

| Phase | Industry-reference refinement |
|---|---|
| Phase 0 | Retain this study as reference architecture; separately confirm workbook rules, organization codes, owners, scenarios, and adoption decisions. |
| Phase 1 | Keep framework interfaces and audit foundations; do not implement generic business-rule scripting. |
| Phase 2 | Make cost classifications, mapping profiles, templates, and rate books version-aware and effective-dated where confirmed. Preserve external identifiers. |
| Phase 3 | Capture planning requirements as supplied; store only costing-relevant well/job/phase context. |
| Phase 4 | Generate versioned cost builds from requirements/templates; record rate selection explicitly and allow manual/bulk override with reason. |
| Phase 5 | Implement a versioned, traceable strategy-based domain engine using confirmed rules only. |
| Phase 6 | Implement a small state-machine core with configurable profiles and role mappings; preserve hard authorization/audit guardrails. |
| Phase 7 | Treat an approved AFE as an immutable snapshot. Add revision/supplement mechanisms only after business confirmation. |
| Phase 8 | Explicitly distinguish field estimates, commitments, accruals, booked actuals, and forecasts. Support reversals and source-document lineage. |
| Phase 9 | Report every cost state through shared dimensions, with drill-through to source/version. |
| Phase 10 | Publish stable reporting views and mapping documentation; keep transactional schema private. |
| Phase 11 | Validate configuration permissions, financial invariants, audit completeness, scale, and full scenario reconciliation. |

## 12. Adoption register

### Adopt as structural principles

- Connected requirement → estimate → AFE → field cost → actual → forecast → reporting chain
- Shared coding dimensions across planned and actual costs
- Separate cost states rather than overwrite-in-place
- Versioned estimates, templates, mappings, rate books, workflows, and forecasts
- Immutable approved AFE snapshots
- Bulk grid and Excel round-trip support
- Effective-dated master/rate data where confirmed
- Source-document lineage and reversible corrections
- Configurable workflows/views within hard financial and security guardrails
- API and reporting boundaries designed for future ERP, PIDX, WITSML-context, and Power BI integrations

### Pending business confirmation

- Exact cost breakdown hierarchy and code depth
- Mandatory line-item dimensions
- Rate selection and vendor precedence
- Currency and exchange-rate treatment
- Contingency, escalation, and rounding
- Supplemental/revised AFE behavior and approval thresholds
- Gross/net ownership, partner balloting, and joint-interest functionality
- Tangible/intangible or tax classifications
- Field estimate versus accrual definitions
- Commitment and invoice matching
- Forecast/EAC methodology
- Probabilistic P10/P50/P90 estimating
- Offline field capture and notifications

### Explicitly excluded

- Well trajectory design
- BHA design
- Hydraulics
- Casing/cement engineering design
- Drilling simulation
- Formation evaluation
- Rig selection or rig optimization logic
- Production accounting or joint-interest billing unless separately approved as future scope

## 13. Architecture test for future changes

A proposed change is acceptable only if all answers below are satisfactory:

1. Can it be traced to an approved requirement, source workbook, standard mapping, or confirmed business decision?
2. Does it preserve previous estimate, AFE, actual, and forecast versions?
3. Can users perform the operation in bulk where volume is material?
4. Is financial logic kept out of Vue components and FastAPI routes?
5. Is the domain calculation deterministic and unit-testable without frameworks?
6. Is configuration versioned, auditable, and permission-controlled?
7. Can the result be reconciled to its input, rate, rule, currency, and source document?
8. Does the change avoid expanding into upstream well-planning logic?
9. Will existing golden scenarios fail loudly if numeric behavior changes?
10. Can Power BI and external integrations remain stable through documented mappings/views?

## 14. Conclusion

The existing project roadmap already follows the dominant global pattern. The main architectural improvement is not to imitate one commercial user interface; it is to formalize **configuration, versioning, cost-state separation, source lineage, and immutable approvals** from the beginning.

This lets the organization change templates, codes, mappings, roles, workflow labels, and report structures later while protecting calculation integrity and historical financial records. Formula behavior will still be implemented only from verified Excel evidence and approved business rules.

## 15. Public references

- Halliburton Well Cost [3](https://www.halliburton.com/en/software/decisionspace-365-enterprise/decisionspace-365-well-construction/well-construction-suite/well-cost-software)
- Halliburton OpenWells Cost Estimate & AFE [2](https://esd.halliburton.com/support/LSM/Drilling/EDMEDTSuite/OpenWells/5000/5000_1/Help/Reports/Cost_Estimate_AFE/Cost_Est_&_AFE_Report.htm)
- Halliburton OpenWells Cost Data [1](https://esd.halliburton.com/support/LSM/Drilling/EDMEDTSuite/OpenWells/5000/5000_1/Help/Interactive_Well_Site/Daily_Operations_Data/cost_data.htm)
- Peloton WellView [3](https://www.peloton.com/products/well-data-lifecycle/wellview)
- Quorum Execute AFE [3](https://www.quorumsoftware.com/solutions/planning-economics-reserves/execute/afe/)
- Quorum Well Operations [4](https://www.quorumsoftware.com/solutions/upstream-on-demand/well-operations/)
- W Energy AFE [1](https://wenergysoftware.com/solutions/afe-authorization-for-expenditure/)
- Resource Energy Solutions AFE Manager [5](https://resourceenergysolutions.com/afe-manager-software/)
- IFS Energy & Resources AFE [1](https://www.ifs.com/en/insights/assets/energy-and-resources-afe)
- PIDX standards [2](https://pidx.org/standards/)
- PPDM well lifecycle data-model reference [1](https://dl.ppdm.org/dl/1882)
- Energistics standards overview [3](https://docs.energistics.org/CTA/CTA_TOPICS/CTA-000-002-0-C-sv2100.html)
- ISO 19008:2026: https://www.iso.org/standard/88670.html
