<script setup lang="ts">
import PageHeader from '~/components/design-system/PageHeader.vue'
definePageMeta({ middleware: 'auth' })
const sections = [
  { id: 'flow', label: 'Data flow' },
  { id: 'master-data', label: '1. Master Data' },
  { id: 'afe', label: '2. AFE' },
  { id: 'estimate', label: '3. AFE Cost Estimates' },
  { id: 'activities', label: '4. Well Activities' },
  { id: 'daily', label: '5. Daily Cost' },
  { id: 'analytics', label: '6. Analytics & Cost Control' },
  { id: 'reports', label: '7. Reports' },
  { id: 'audit', label: '8. Audit & Assurance' },
]
</script>

<template>
  <div class="help-page">
    <PageHeader title="Help & User Manual" description="The end-to-end workflow from configured Master Data to AFE planning, priced estimates, Daily Cost actuals, reports and audit." />
    <div class="help-layout">
      <nav class="help-toc" aria-label="Help contents"><a v-for="section in sections" :key="section.id" :href="`#${section.id}`">{{ section.label }}</a></nav>
      <main class="help-body">
        <section id="flow" class="help-section">
          <h2>One active data flow</h2>
          <ol class="help-flow"><li><strong>Master Data</strong> supplies user-configured classifications, cost codes, units, sections, vendors and catalogue references.</li><li><strong>AFE</strong> defines the well budget, section/phase plan and classified cost scope.</li><li><strong>AFE Cost Estimates</strong> saves the well-scoped rate for each AFE line.</li><li><strong>Well Activities</strong> defines Planned/NPT/UPA accountability and responsible parties.</li><li><strong>Daily Cost</strong> records actual operational and quantity charges using AFE estimate rates.</li><li><strong>Cost Analytics, Cost Control and Reports</strong> compare AFE plan and estimate directly with Daily Cost actuals.</li></ol>
        </section>

        <section id="master-data" class="help-section"><h2>1. Master Data</h2><p>Configure the classification hierarchy first: Primary → Secondary → Tertiary. AFE lines select the Primary and Secondary categories you created; Cost Estimates display those exact values rather than guessing a service/tangible/other type.</p><ul class="help-list"><li>Configure cost categories and cost codes against the same classification.</li><li>Configure units, hole sections, vendors and phases before planning an AFE.</li><li>Use Administration → Dropdown Sources when a picker must read another approved master-data source.</li><li>Every master-data register supports bulk entry, import, export and print.</li></ul></section>

        <section id="afe" class="help-section"><h2>2. AFE</h2><p>Create Project → Well → AFE. Enter the authorised budget, planned depth, sections and phases. Then add compact cost-scope lines by selecting the user-configured Primary Category, Secondary Category, cost code, type, rate basis and section.</p><ul class="help-list"><li><strong>AFE Lines are scope only:</strong> do not enter quantity, UOM, usage/day or a consumable total here.</li><li>For consumables, select <strong>Per unit</strong>; the actual quantity and UOM are entered against the operational day in Daily Cost.</li><li>Submit when the scope is ready. Reopening requires remarks and is audited. Print produces the current saved AFE scope.</li></ul></section>

        <section id="estimate" class="help-section"><h2>3. AFE Cost Estimates</h2><p>Select a well and a <strong>submitted</strong> AFE, then enter one estimated total rate, optional vendor and remarks for every AFE line. Scope-only lines use that rate as their estimated amount. Summaries use the configured Primary/Secondary categories, hole sections and cost codes.</p><p>The saved rate is the default in Daily Cost. A Daily Cost override is allowed for an exceptional day and remains visible in that day record. Print and export use the current submitted AFE Cost Estimate only.</p></section>

        <section id="activities" class="help-section"><h2>4. Well Activities</h2><p>Configure well-specific sub-activities under the master activities (for example Planned, NPT and UPA), including the responsible party. Daily Cost requires the day activity so reports can show cost accountability.</p></section>

        <section id="daily" class="help-section"><h2>5. Daily Cost</h2><p>Daily Cost loads only lines from the governing submitted AFE and their rates from AFE Cost Estimates. The selected AFE rate basis decides the entry calculation:</p><div class="help-table-wrap"><table class="help-table"><thead><tr><th>Rate basis</th><th>Daily calculation</th></tr></thead><tbody><tr><td>Daily</td><td>Hours ÷ 24 × estimate rate</td></tr><tr><td>Per section / per service / fixed</td><td>Estimate rate once for the entered charge</td></tr><tr><td>Per unit</td><td>Actual used quantity × estimate rate; choose the actual UOM here</td></tr></tbody></table></div><p>Save the operational summary, phase, section, depth, progress and activity. The page recalculates cumulative actual, remaining AFE budget, burn rate and forecast.</p></section>

        <section id="analytics" class="help-section"><h2>6. Cost Analytics & Cost Control</h2><p><strong>Cost Analytics</strong> provides charts and tables by date, week, month, section, phase, activity and responsible party. <strong>Cost Control</strong> provides the reconciliation view:</p><p><code>AFE budget → AFE Cost Estimate → Daily Cost actual → remaining/variance</code></p><p>Both pages export the same active source chain to Excel; Cost Control also prints a control sheet.</p></section>

        <section id="reports" class="help-section"><h2>7. Reports</h2><p>Select and generate any of these live reports: AFE Register, AFE Cost Estimate Detail, Daily Cost Register, Cost Performance, or Well Activities & Accountability. Filter by project, well, AFE and—where relevant—date range. The displayed result can be printed or exported to Excel.</p></section>

        <section id="audit" class="help-section"><h2>8. Audit Log & Assurance</h2><p>The Audit Log is append-only and records actor, time, action, entity and details. Filter the complete trail, then print or export all matching rows—not only the current page. Assurance checks that AFE classifications, estimate rates, Daily Cost sources/totals and Well Activity links remain consistent.</p></section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.help-page { width: min(1540px, 100%); margin: 0 auto; }
.help-layout { display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 24px; align-items: start; }
.help-toc { position: sticky; top: 86px; display: grid; gap: .2rem; padding: .8rem; border: 1px solid var(--surface-border); border-radius: 10px; background: var(--surface-card); }
.help-toc a { padding: .55rem .7rem; border-radius: 6px; color: var(--text-color); text-decoration: none; } .help-toc a:hover { background: var(--surface-hover); color: var(--primary-color); }
.help-body { min-width: 0; } .help-section { scroll-margin-top: 90px; margin-bottom: 1rem; padding: 1.2rem 1.4rem; border: 1px solid var(--surface-border); border-radius: 10px; background: var(--surface-card); }
.help-section h2 { margin-top: 0; } .help-flow, .help-list { display: grid; gap: .5rem; line-height: 1.55; }
.help-table { width: 100%; border-collapse: collapse; } .help-table th, .help-table td { padding: .65rem; border: 1px solid var(--surface-border); text-align: left; } .help-table th { background: var(--surface-100); }
@media (max-width: 850px) { .help-layout { grid-template-columns: 1fr; } .help-toc { position: static; grid-template-columns: repeat(2, 1fr); } }
</style>
