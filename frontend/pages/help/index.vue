<script setup lang="ts">
/** Help & user manual — the end-to-end guide to how the modules link together. */
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })

const sections = [
  { id: 'overview', label: 'How the modules link together' },
  { id: 'workflow', label: 'Recommended workflow' },
  { id: 'master-data', label: 'Master Data — start here' },
  { id: 'afe-backbone', label: 'AFE — the costing backbone' },
  { id: 'reopen-afe', label: 'Reopening submitted AFEs & audit' },
  { id: 'deleted-afes', label: 'Deleted AFEs & recovery' },
  { id: 'audit-log', label: 'Audit Log' },
  { id: 'cost-builder-vs-daily', label: 'AFE Cost Estimates vs Daily Cost' },
  { id: 'daily-cost', label: 'Daily Cost Entry & analytics' },
  { id: 'cost-control', label: 'Cost Control & postings' },
  { id: 'reports', label: 'Reports & export' },
  { id: 'assurance', label: 'Assurance' },
  { id: 'administration', label: 'Administration' },
]
</script>

<template>
  <div class="help-page">
    <PageHeader
      title="Help & User Manual"
      description="Comprehensive guide explaining module roles, AFE backbone planning, reopening submitted AFEs, AFE Cost Estimates pricing, Daily Cost tracking, and cost analytics."
    />

    <div class="help-layout">
      <nav class="help-toc" aria-label="Help contents">
        <a v-for="section in sections" :key="section.id" :href="`#${section.id}`">{{ section.label }}</a>
      </nav>

      <main class="help-body">
        <!-- Overview -->
        <section id="overview" class="help-section">
          <h2>How the modules link together</h2>
          <p>
            The application is an end-to-end well costing and execution pipeline. Information flows in a structured sequence:
          </p>
          <ol class="help-flow">
            <li><strong>Master Data</strong> — reference catalogues: services, tangibles, mud chemicals, cement additives, vendors, units, and rates.</li>
            <li><strong>AFE (Authorisation for Expenditure)</strong> — the technical and financial backbone of the well: budget amount, hole sections, phases, planned days, and depths.</li>
            <li><strong>AFE Cost Estimates</strong> — prices the AFE: every AFE line receives its well-scoped unit rate here, and the saved rates are the single source of rates for daily cost entry. Export and print the priced AFE for records.</li>
            <li><strong>Daily Cost</strong> — operational field tracking: records daily service hours (hours/24 = operating days × rate) and chemical usage (qty × unit rate), comparing live spend against the AFE budget and generating end-of-well forecasts.</li>
            <li><strong>Cost Control</strong> — stages and posts multi-state financial transactions (field estimates, commitments, accruals, actuals, forecasts).</li>
            <li><strong>Reports & Assurance</strong> — multidimensional variance analytics and formal approval governance.</li>
          </ol>
        </section>

        <!-- Workflow -->
        <section id="workflow" class="help-section">
          <h2>Recommended workflow</h2>
          <ol class="help-steps">
            <li>Set up <strong>Master Data</strong>: units, currencies, hole sections, cost codes, vendors, services, and chemicals.</li>
            <li>Open <strong>AFE</strong>: register the <strong>Project</strong>, then the <strong>Well</strong>.</li>
            <li>Create the <strong>AFE</strong> on the AFEs tab: enter the budget amount and configure the <strong>Well Section & Phase Breakdown</strong> (hole sizes, configurable phases, planned days, and depths).</li>
            <li>On the <strong>AFE Lines</strong> tab, add planned services and chemicals. (Daily consumption chemicals multiply daily usage by the section's planned days).</li>
            <li><strong>Submit</strong> the AFE. If changes are later needed, use <strong>Reopen AFE</strong> with mandatory remarks.</li>
            <li>Open <strong>AFE Cost Estimates</strong> and input the well-scoped unit rate for every AFE line; export or print the priced AFE for records.</li>
            <li>Configure the <strong>Well Activities</strong> page (Planned, NPT-1, UPA-1, …) — daily cost entry requires the day's activity type so Planned / NPT / UPA spend is accounted properly.</li>
            <li>During drilling/operations, open <strong>Daily Cost</strong> to record daily service hours and chemical usage. Unit rates come from the AFE Cost Estimates (override available per line), tracking burn rate, balance amount, and 5/7-day trends.</li>
            <li>Review the planned-versus-actual comparison in <strong>Cost Analytics</strong> — section-wise, activity-wise, phase-wise, date-wise, cumulative, week-wise, and month-wise — plus reconciliation charts in <strong>Reports</strong>.</li>
          </ol>
        </section>

        <!-- Master Data -->
        <section id="master-data" class="help-section">
          <h2>Master Data — start here</h2>
          <p>
            Master Data provides the foundational reference records used across the entire platform:
          </p>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr><th>Page</th><th>What it holds</th><th>Used by</th></tr>
              </thead>
              <tbody>
                <tr><td>Units of Measure</td><td>UOMs such as M, FT, DAY, EA, BBL, SACK</td><td>Quantities, depths, rates</td></tr>
                <tr><td>Currencies</td><td>Currency codes such as USD, GBP, EUR</td><td>Rates, orders, reporting</td></tr>
                <tr><td>Hole Sections</td><td>Well hole sizes (e.g. 36", 26", 17-1/2", 12-1/4", 8-1/2", 6")</td><td>AFE section planning & lines</td></tr>
                <tr><td>Cost Categories & Codes</td><td>Classification hierarchy (e.g. Rig, Fluids, Directional)</td><td>AFE lines, Daily Cost, Postings</td></tr>
                <tr><td>Vendors</td><td>Suppliers and service providers</td><td>Rate books and purchase orders</td></tr>
                <tr><td>Services & Consumables</td><td>Catalog of services, mud chemicals, cement additives</td><td>AFE lines and Daily Cost logs</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- AFE Backbone -->
        <section id="afe-backbone" class="help-section">
          <h2>AFE — The Costing Backbone</h2>
          <p>
            The AFE is the central technical and financial anchor for the well:
          </p>
          <ul class="help-list">
            <li><strong>Budget Amount:</strong> The authorised spending limit for the well.</li>
            <li><strong>Section & Phase Breakdown:</strong> Established on the <strong>AFEs tab</strong> before entering line items. Users enter the hole sections, operational phases (e.g. Drilling, Logging, Casing & Cementing, Completion), planned days, and planned depth intervals.</li>
            <li><strong>Configurable Phases:</strong> Operational phases are fully configurable by the user via the "Configure Phases" button.</li>
            <li><strong>Streamlined AFE Lines:</strong> On the AFE lines grid, planned days and depths are not repeated on every row. Chemical daily usage automatically multiplies by the configured section planned days.</li>
          </ul>
        </section>

        <!-- Reopen AFE -->
        <section id="reopen-afe" class="help-section">
          <h2>Reopening Submitted AFEs & Audit Trail</h2>
          <p>
            Submitted AFEs can be edited when operational changes occur:
          </p>
          <ul class="help-list">
            <li>Click <strong>"Reopen AFE"</strong> on the AFEs tab or AFE Lines tab.</li>
            <li>A mandatory <strong>Remarks / Reason</strong> must be provided explaining the purpose of the revision.</li>
            <li>The system records an immutable <strong>Audit Log entry</strong> capturing who reopened the AFE, the timestamp, previous status, and the remarks.</li>
            <li>Once reopened, lines, sections, and rates can be freely modified. All changes remain <strong>well-scoped</strong> (affecting only that well).</li>
            <li>When modifications are complete, click <strong>"Resubmit"</strong> to seal the updated baseline.</li>
          </ul>
        </section>

        <!-- Deleted AFEs -->
        <section id="deleted-afes" class="help-section">
          <h2>Deleted AFEs & Recovery</h2>
          <p>
            Both draft and submitted AFEs can be soft-deleted. Hard-deletion is only allowed from the Deleted AFEs area.
          </p>
          <ul class="help-list">
            <li><strong>Soft-delete:</strong> Click the trash icon on any AFE (draft or submitted). The AFE is moved to the <strong>Deleted AFEs</strong> tab and remains recoverable with all its lines, sections, and audit history intact.</li>
            <li><strong>Deleted AFEs tab:</strong> Lists every soft-deleted AFE with its deleted timestamp. From here you can <strong>Recover</strong> or <strong>Delete forever</strong>.</li>
            <li><strong>Recovery guard:</strong> If any active AFE already exists on the main AFEs tab, recovery is blocked — you must delete the active AFE first. This prevents duplicate active AFEs and keeps the financial backbone unambiguous.</li>
            <li><strong>Permanent delete:</strong> In Deleted AFEs, click <strong>Delete forever</strong> to hard-delete the AFE and its orphaned lines/sections. This action is logged to the global Audit Log.</li>
            <li><strong>Master Data:</strong> Reference records (units, vendors, services, hole sections, etc.) follow the same pattern: soft-delete via the grid, then recover or hard-delete when <strong>Include inactive</strong> is enabled. The grid shows <strong>Recover</strong> and <strong>Permanently delete</strong> for inactive rows, and recovery is blocked if an active record with the same code already exists.</li>
          </ul>
        </section>

        <!-- Audit Log -->
        <section id="audit-log" class="help-section">
          <h2>Audit Log</h2>
          <p>
            Every user action is recorded to an immutable <strong>Audit Log</strong> for compliance, displayed at <strong>Audit Log</strong> in the sidebar.
          </p>
          <ul class="help-list">
            <li><strong>Logged from login onward:</strong> login, create, update, submit, reopen, resubmit, soft-delete, recover, hard-delete, and bulk operations across AFE, projects, wells, master data, phases, and rates.</li>
            <li><strong>What is stored:</strong> actor (email), timestamp, action, entity type, entity code, and a JSON details payload (e.g. previous status, remarks, or changed fields).</li>
            <li><strong>Filtering:</strong> Search by actor, entity, or code; filter by action or entity type; paginate through history. The log is append-only and never edited.</li>
            <li><strong>AFE audit vs global audit:</strong> The AFE detail also shows a per-AFE trail (created, submitted, reopened, soft-deleted, recovered). The global Audit Log aggregates these plus every master-data change for enterprise-wide oversight.</li>
          </ul>
        </section>

        <!-- AFE Cost Estimates vs Daily Cost -->
        <section id="cost-builder-vs-daily" class="help-section">
          <h2>AFE Cost Estimates vs Daily Cost Entry</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr><th>Feature</th><th>AFE Cost Estimates (Planning)</th><th>Daily Cost Entry (Execution)</th></tr>
              </thead>
              <tbody>
                <tr><td><strong>Purpose</strong></td><td>Prices the AFE: well-scoped unit rates for every AFE line</td><td>Real-time operational daily cost tracking</td></tr>
                <tr><td><strong>Timing</strong></td><td>Planning phase, after AFE lines are added</td><td>Daily during active drilling &amp; completion</td></tr>
                <tr><td><strong>Input data</strong></td><td>Unit rate (and optional vendor/remarks) per AFE line</td><td>Service hours (0-24), chemical quantities, activity type (Planned / NPT / UPA)</td></tr>
                <tr><td><strong>Calculation</strong></td><td>Quantity × unit rate = estimated amount; totals by section, item type, and cost code</td><td>Hours/24 × rate basis; Qty × unit rate; cumulative spend. Rates come from the AFE Cost Estimates with per-line override</td></tr>
                <tr><td><strong>Key Output</strong></td><td>The priced AFE — exportable and printable for records</td><td>Daily burn rate, remaining AFE balance, end-of-well forecast, daily reports</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- Daily Cost -->
        <section id="daily-cost" class="help-section">
          <h2>Daily Cost Entry & Comparative Analytics</h2>
          <p>
            The <strong>Daily Cost</strong> module provides live rig-site operational tracking:
          </p>
          <ul class="help-list">
            <li><strong>Activity Type (mandatory):</strong> Each day log records its activity type — a well-scoped sub-activity (e.g. Planned, NPT-1, UPA-1) configured on the <strong>Well Activities</strong> page. This accounts every cost to Planned, NPT, or UPA and its responsible party.</li>
            <li><strong>Unit Rates:</strong> Rates are read from the <strong>AFE Cost Estimates</strong> of the well's AFE — the single source of unit rates. A per-line override remains available for exceptional days and is stored with the entry.</li>
            <li><strong>Service Hours Calculation:</strong> User enters the hours a service was active on that date (e.g. 12h, 24h). The system divides by 24 to compute operating days (e.g. 12h = 0.5000 days), and multiplies by the daily rate (or charges fixed / per-section / per-service rate).</li>
            <li><strong>Chemicals & Additives:</strong> User enters the quantity of mud chemicals or cement additives used; the system multiplies by unit rate.</li>
            <li><strong>AFE Balance Comparison:</strong> Live calculation of <code>Balance = AFE Budget - Cumulative Actual Spend</code>.</li>
            <li><strong>Burn Rate & Forecast:</strong> Calculates average daily burn rate (<code>Cumulative / Days Elapsed</code>) and projects total cost at completion (<code>Cumulative + Remaining Planned Days × Burn Rate</code>).</li>
            <li><strong>Trend & Drill-Through Charts:</strong> Toggle between Last 5 Days, Last 7 Days, and Full Drill-Through to analyze service consumption and daily spend trends.</li>
            <li><strong>Daily Reports:</strong> Every saved day log can be printed or exported as a daily cost report, and the full daily cost register exports to Excel for records.</li>
          </ul>
        </section>

        <!-- Cost Control -->
        <section id="cost-control" class="help-section">
          <h2>Cost Control & Staging</h2>
          <p>
            Cost Control stages and reconciles financial transactions across distinct recognition states:
            commitments (POs/SOs), accruals (earned services), booked actuals (invoices), and financial forecasts.
          </p>
        </section>

        <!-- Reports -->
        <section id="reports" class="help-section">
          <h2>Reports</h2>
          <p>
            Reports join plan dimensions (from the AFE and its Cost Estimates) with actual spend (from Daily Cost and Cost Control) across shared dimensions: project, well, AFE, cost code, vendor, and currency.
          </p>
        </section>

        <!-- Assurance -->
        <section id="assurance" class="help-section">
          <h2>Assurance</h2>
          <p>
            Tracks review, verification, and sign-off workflows for cost estimates and AFE revisions.
          </p>
        </section>

        <!-- Administration -->
        <section id="administration" class="help-section">
          <h2>Administration</h2>
          <p>
            Enterprise costing hierarchy, organization nodes, cost structures, and corporate rate books.
          </p>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.help-page {
  width: min(1540px, 100%);
  margin: 0 auto;
}

.help-layout {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.help-toc {
  position: sticky;
  top: calc(var(--layout-topbar-height) + 16px);
  display: grid;
  gap: 2px;
  padding: 10px;
  border: 1px solid var(--app-border);
  border-radius: 11px;
  background: white;
  box-shadow: var(--app-shadow);
}

.help-toc a {
  padding: 7px 10px;
  border-radius: 7px;
  color: var(--app-muted);
  font-size: .78rem;
  font-weight: 600;
  text-decoration: none;
}

.help-toc a:hover {
  background: #eef3f6;
  color: var(--app-ink);
}

.help-body {
  display: grid;
  gap: 18px;
  min-width: 0;
}

.help-section {
  padding: 20px 24px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: white;
  box-shadow: var(--app-shadow);
  scroll-margin-top: calc(var(--layout-topbar-height) + 16px);
}

.help-section h2 {
  margin: 0 0 12px;
  font-size: 1.12rem;
}

.help-section p {
  margin: 0 0 12px;
  color: var(--app-ink);
  line-height: 1.65;
}

.help-flow,
.help-steps {
  margin: 0 0 12px;
  padding-left: 20px;
  line-height: 1.7;
}

.help-flow li,
.help-steps li {
  margin-bottom: 6px;
}

.help-list {
  margin: 0 0 12px;
  padding-left: 20px;
  line-height: 1.7;
}

.help-list li {
  margin-bottom: 6px;
}

.help-table-wrap {
  overflow-x: auto;
  margin-bottom: 12px;
}

.help-table {
  width: 100%;
  border-collapse: collapse;
  font-size: .8rem;
}

.help-table th,
.help-table td {
  padding: 8px 10px;
  border: 1px solid var(--app-border);
  text-align: left;
  vertical-align: top;
}

.help-table thead th {
  background: #eef3f6;
  font-size: .72rem;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: .04em;
}

.help-note {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 10px 14px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  color: #1e40af;
  font-size: .8rem;
}

.help-note .pi {
  margin-top: 2px;
  flex-shrink: 0;
}

@media (max-width: 900px) {
  .help-layout {
    grid-template-columns: 1fr;
  }

  .help-toc {
    position: static;
  }
}
</style>
