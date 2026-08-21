<script setup lang="ts">
/** Help & user manual — the end-to-end guide to how the modules link together. */
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })

const sections = [
  { id: 'overview', label: 'How the modules link together' },
  { id: 'workflow', label: 'Recommended workflow' },
  { id: 'master-data', label: 'Master Data — start here' },
  { id: 'cost-codes', label: 'Cost codes explained' },
  { id: 'afe', label: 'AFE — projects, wells, AFEs, lines' },
  { id: 'afe-data', label: 'What data an AFE line needs' },
  { id: 'cost-builder', label: 'Cost Builder' },
  { id: 'cost-control', label: 'Cost Control' },
  { id: 'reports', label: 'Reports' },
  { id: 'assurance', label: 'Assurance' },
  { id: 'administration', label: 'Administration' },
]
</script>

<template>
  <div class="help-page">
    <PageHeader
      title="Help & User Manual"
      description="How the modules fit together, the order to work in, and what each screen needs before you can make an entry."
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
            The application is a single data pipeline. Information flows in one direction, and each module
            consumes what the previous one produced — so it is important to work in order.
          </p>
          <ol class="help-flow">
            <li><strong>Master Data</strong> — the reference lists every other module reads from.</li>
            <li><strong>AFE</strong> — the authorised scope, built from those reference lists.</li>
            <li><strong>Cost Builder</strong> — prices the AFE lines to produce a cost build.</li>
            <li><strong>Cost Control</strong> — posts the actuals against that plan.</li>
            <li><strong>Reports</strong> — compares plan vs actual across the shared dimensions.</li>
            <li><strong>Assurance</strong> — tracks review and approval state throughout.</li>
          </ol>
          <p>
            The key rule: <strong>Master Data comes first</strong>. The AFE's dropdowns — items, cost codes,
            units, sections, categories — are all populated from Master Data. Until those lists exist, there is
            nothing to select on an AFE line. That is why Master Data sits immediately after the Dashboard in the menu.
          </p>
        </section>

        <!-- Workflow -->
        <section id="workflow" class="help-section">
          <h2>Recommended workflow</h2>
          <ol class="help-steps">
            <li>Configure <strong>Master Data</strong>: units, currencies, categories, hole sections, cost categories, cost codes, vendors, services, tangibles, consumables, and rates.</li>
            <li>Open <strong>AFE</strong> and register a <strong>project</strong>, then its <strong>wells</strong>.</li>
            <li>Raise an <strong>AFE</strong> against a well and add its <strong>lines</strong>.</li>
            <li><strong>Submit</strong> the AFE so it becomes available to the Cost Builder.</li>
            <li>Build and price the cost in <strong>Cost Builder</strong>.</li>
            <li>Post actuals in <strong>Cost Control</strong> as work proceeds.</li>
            <li>Review the comparison in <strong>Reports</strong>.</li>
          </ol>
        </section>

        <!-- Master Data -->
        <section id="master-data" class="help-section">
          <h2>Master Data — start here</h2>
          <p>
            Master Data is a set of tabs under one menu. Configure them roughly in the order they appear, because
            later lists reference earlier ones. Every page works the same way: a grid you can edit inline, bulk-add,
            paste from Excel, import, or export.
          </p>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr><th>Page</th><th>What it holds</th><th>Used by</th></tr>
              </thead>
              <tbody>
                <tr><td>Units of Measure</td><td>UOMs such as M, DAY, EA, BBL</td><td>Every quantity and rate</td></tr>
                <tr><td>Currencies</td><td>Currency codes such as USD, GBP</td><td>Rates, orders, reports</td></tr>
                <tr><td>Item Categories / Sub Categories</td><td>Groupings such as Bits, Casings</td><td>Classifying catalogue items</td></tr>
                <tr><td>Hole Sections</td><td>Drilling sections such as 17-1/2", 12-1/4"</td><td>Section-charged AFE lines</td></tr>
                <tr><td>Cost Categories</td><td>Top-level cost groups such as Drilling, Services</td><td>Grouping cost codes</td></tr>
                <tr><td>Cost Codes</td><td>The identifiers each AFE line is charged to</td><td>AFE lines, reports, postings</td></tr>
                <tr><td>Vendors</td><td>Suppliers (3rd party or in-house)</td><td>Orders and rates</td></tr>
                <tr><td>Service / Purchase Orders</td><td>The contracts vendors work under</td><td>Rates and procurement</td></tr>
                <tr><td>Services, Tangibles, Consumables</td><td>The catalogue of items you can plan</td><td>AFE lines</td></tr>
                <tr><td>Tangible Rates / Rate Revisions</td><td>Prices for tangibles and consumables</td><td>Cost Builder</td></tr>
              </tbody>
            </table>
          </div>
          <p class="help-note">
            <i class="pi pi-info-circle" aria-hidden="true" />
            Each catalogue item (a service, tangible, or chemical) can carry a default cost code and default unit.
            Set those so AFE lines pre-fill correctly when the item is picked.
          </p>
        </section>

        <!-- Cost codes -->
        <section id="cost-codes" class="help-section">
          <h2>Cost codes explained</h2>
          <p>
            A <strong>cost code</strong> is the short, stable identifier that says <em>where a cost belongs</em>.
            It is not a price — it is the classification every AFE line carries, so planned and actual spend can be
            grouped and compared like-for-like.
          </p>
          <ul class="help-list">
            <li><strong>Cost category</strong> groups several codes (for example “Drilling”).</li>
            <li><strong>Cost code</strong> sits under a category (for example “2010 – Rig day rate”).</li>
            <li>Every AFE line is charged to exactly one cost code.</li>
            <li>Cost builds roll line totals up by code and category; reports filter on them.</li>
          </ul>
          <p>To configure: create <strong>Cost Categories</strong> first, then add <strong>Cost Codes</strong> and pick a category for each.</p>
        </section>

        <!-- AFE -->
        <section id="afe" class="help-section">
          <h2>AFE — projects, wells, AFEs, lines</h2>
          <p>The AFE page is split into four tabs that follow the dependency order:</p>
          <ol class="help-list">
            <li><strong>Projects</strong> — add the top-level grouping (e.g. a drilling campaign).</li>
            <li><strong>Wells</strong> — add wells and assign each to a project.</li>
            <li><strong>AFEs</strong> — raise an AFE against a well (code, title, description).</li>
            <li><strong>AFE Lines</strong> — pick the AFE and enter its line items.</li>
          </ol>
          <p>
            A draft AFE can be edited freely. When it is complete, choose <strong>Submit</strong>: it becomes
            read-only and appears in the Cost Builder. A draft AFE can be deleted; a submitted one cannot.
          </p>
        </section>

        <!-- AFE data -->
        <section id="afe-data" class="help-section">
          <h2>What data an AFE line needs</h2>
          <p>Each line records a single planned item and how it will be charged. The required fields are:</p>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead><tr><th>Field</th><th>Where it comes from</th><th>Notes</th></tr></thead>
              <tbody>
                <tr><td>Item</td><td>Master Data catalogue (services, tangibles, materials, equipment, chemicals)</td><td>Pre-fills the rate basis, unit, and cost code when set on the item.</td></tr>
                <tr><td>Cost code</td><td>Master Data › Cost Codes</td><td>Mandatory — classifies the line.</td></tr>
                <tr><td>Rate basis</td><td>Item default, overridable per line</td><td>Daily, per section, per service, fixed, per unit, or daily usage.</td></tr>
                <tr><td>Section</td><td>Master Data › Hole Sections</td><td>Required only for lines charged per section.</td></tr>
                <tr><td>Quantity / Unit</td><td>You enter; unit from Master Data › Units</td><td>Chemicals on daily usage compute quantity = usage/day × days.</td></tr>
                <tr><td>Usage / day &amp; planned days</td><td>You enter</td><td>For daily-consumption lines only.</td></tr>
                <tr><td>Depth from / to / unit</td><td>You enter; unit from Master Data › Units</td><td>Optional depth range context.</td></tr>
              </tbody>
            </table>
          </div>
          <p class="help-note">
            <i class="pi pi-info-circle" aria-hidden="true" />
            If a chemical line's quantity differs from the computed total, you must give an override reason.
          </p>
        </section>

        <!-- Cost Builder -->
        <section id="cost-builder" class="help-section">
          <h2>Cost Builder</h2>
          <p>
            Once an AFE is submitted, open the Cost Builder to turn it into a cost build. Assign a vendor and rate to
            each line (rates come from Master Data), set contingency and escalation assumptions, and save the build.
            Submitted AFEs are listed automatically; pick one to start.
          </p>
        </section>

        <!-- Cost Control -->
        <section id="cost-control" class="help-section">
          <h2>Cost Control</h2>
          <p>
            Post the actual costs as they happen — commitments, accruals, actuals, and forecasts — each tagged with
            the same project, well, AFE, and cost code used at planning. Matching the dimensions here is what lets
            Reports compare plan against actual.
          </p>
        </section>

        <!-- Reports -->
        <section id="reports" class="help-section">
          <h2>Reports</h2>
          <p>
            Reports join the plan (from AFEs and cost builds) with the actuals (from Cost Control) across the shared
            dimensions: project, well, AFE, cost state, cost code, vendor, and currency. Filter on any of them and
            export to Excel for distribution.
          </p>
        </section>

        <!-- Assurance -->
        <section id="assurance" class="help-section">
          <h2>Assurance</h2>
          <p>
            Assurance records the review and approval trail for cost builds — who reviewed, what state it is in, and
            any notes attached along the way. It exists so a financial figure can always be traced back to its
            approval.
          </p>
        </section>

        <!-- Administration -->
        <section id="administration" class="help-section">
          <h2>Administration</h2>
          <p>
            Administration holds the enterprise-level costing model: the organisation hierarchy, cost structures,
            rate books, estimate templates, and reporting mappings. Configuration here is created as versioned,
            audited drafts until separately published, so changing it never silently rewrites history.
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
  grid-template-columns: 220px minmax(0, 1fr);
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
