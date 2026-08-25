<script setup lang="ts">
/**
 * Cost Control is a read-only reconciliation workspace over the active chain:
 * AFE budget → AFE Cost Estimate → Daily Cost actuals.
 */
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { ProjectRecord, WellRecord } from '~/types/afe'
import type { ComparisonBucket, DailyCostComparison } from '~/types/dailyCost'
import { downloadBlob } from '~/utils/download'
import { escapeHtml, formatMoneyCell, printDocument } from '~/utils/printDocument'

definePageMeta({ middleware: 'auth' })

const api = useDailyCost()
const afeApi = useAfe()
const projects = ref<ProjectRecord[]>([])
const wells = ref<WellRecord[]>([])
const projectId = ref<string | null>(null)
const wellId = ref('')
const comparison = ref<DailyCostComparison | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const activeTab = ref('date')

const wellOptions = computed(() => projectId.value
  ? wells.value.filter(well => well.project_id === projectId.value)
  : wells.value)
const budgetUsed = computed(() => {
  const budget = Number(comparison.value?.afe_budget ?? 0)
  return budget > 0 ? Number(comparison.value?.cumulative_actual_cost ?? 0) / budget * 100 : 0
})
const controlStatus = computed(() => {
  if (!comparison.value?.afe_id) return { label: 'AFE required', severity: 'warn' }
  if (Number(comparison.value.variance_to_budget) < 0) return { label: 'Over budget', severity: 'danger' }
  if (budgetUsed.value >= 90) return { label: 'Watch', severity: 'warn' }
  return { label: 'Within budget', severity: 'success' }
})

function money(value: string | number | null | undefined): string {
  return formatMoneyCell(value)
}

function onProjectChange(): void {
  if (wellId.value && !wellOptions.value.some(item => item.id === wellId.value)) {
    wellId.value = ''
    comparison.value = null
  }
}

async function loadComparison(): Promise<void> {
  if (!wellId.value) return
  loading.value = true
  error.value = null
  try {
    comparison.value = await api.getComparison(wellId.value)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Cost control data could not be loaded.'
    comparison.value = null
  }
  finally { loading.value = false }
}

async function exportExcel(): Promise<void> {
  if (!wellId.value) return
  try {
    downloadBlob(await api.exportComparison(wellId.value), `cost-control-${comparison.value?.well_code ?? 'well'}.xlsx`)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The cost control export failed.'
  }
}

function bucketRows(title: string, values: ComparisonBucket[]): string {
  return `<h2>${escapeHtml(title)}</h2><table><thead><tr><th>Group</th><th class="num">Actual</th><th class="num">Planned</th><th class="num">Variance</th></tr></thead><tbody>${values.map(item => `<tr><td>${escapeHtml(item.label)}</td><td class="num">${money(item.total_cost)}</td><td class="num">${item.planned_cost == null ? '—' : money(item.planned_cost)}</td><td class="num">${item.variance == null ? '—' : money(item.variance)}</td></tr>`).join('')}</tbody></table>`
}

function printControl(): void {
  const detail = comparison.value
  if (!detail) return
  const meta = [
    ['Well', `${detail.well_code ?? ''} — ${detail.well_name ?? ''}`],
    ['Governing AFE', detail.afe_code ?? 'No AFE'],
    ['AFE budget', `$${money(detail.afe_budget)}`],
    ['AFE cost estimate', `$${money(detail.estimate_total)}`],
    ['Daily Cost actual', `$${money(detail.cumulative_actual_cost)}`],
    ['Budget remaining', `$${money(detail.variance_to_budget)}`],
  ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('')
  const daily = detail.by_date.map(item => `<tr><td>${escapeHtml(item.entry_date)}</td><td>${escapeHtml(item.phase ?? '—')}</td><td>${escapeHtml(item.activity_name ?? '—')}</td><td class="num">${money(item.daily_cost)}</td><td class="num">${money(item.cumulative_cost)}</td><td class="num">${item.planned_cumulative == null ? '—' : money(item.planned_cumulative)}</td></tr>`).join('')
  printDocument(`Cost Control ${detail.well_code ?? ''}`, `
    <h1>COST CONTROL</h1><p class="doc-subtitle">AFE and AFE Cost Estimate reconciled directly with Daily Cost actuals.</p>
    <div class="meta-grid">${meta}</div>
    <h2>Daily reconciliation</h2><table><thead><tr><th>Date</th><th>Phase</th><th>Activity</th><th class="num">Daily actual</th><th class="num">Cumulative</th><th class="num">Planned cumulative</th></tr></thead><tbody>${daily}</tbody></table>
    ${bucketRows('By hole section', detail.by_section)}${bucketRows('By activity', detail.by_activity)}
    <p class="print-footer">Printed ${new Date().toLocaleString()}.</p>
  `)
}

onMounted(async () => {
  try {
    const [projectPage, wellPage] = await Promise.all([afeApi.listProjects(), afeApi.listWells()])
    projects.value = projectPage.items.filter(item => item.is_active)
    wells.value = wellPage.items.filter(item => item.is_active)
    if (wells.value[0]) {
      wellId.value = wells.value[0].id
      await loadComparison()
    }
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Cost control references could not be loaded.'
  }
})
</script>

<template>
  <div class="cost-control-page">
    <PageHeader
      title="Cost Control"
      description="Control well spend using the governing AFE budget, priced AFE Cost Estimate and actual Daily Cost entries."
    >
      <template #actions>
        <Tag v-if="comparison" :value="controlStatus.label" :severity="controlStatus.severity as any" />
        <Button label="Print" icon="pi pi-print" outlined :disabled="!comparison" @click="printControl" />
        <Button label="Export Excel" icon="pi pi-file-excel" outlined :disabled="!comparison" @click="exportExcel" />
        <Button label="Refresh" icon="pi pi-refresh" :loading="loading" :disabled="!wellId" @click="loadComparison" />
      </template>
    </PageHeader>

    <Message v-if="error" severity="error" closable @close="error = null">{{ error }}</Message>
    <Message v-if="comparison && !comparison.afe_id" severity="warn" :closable="false">This well has no governing AFE. Create and price an AFE before controlling actual spend.</Message>

    <section class="control-selector bulk-grid-panel">
      <label>Project<Select v-model="projectId" :options="projects" option-label="code" option-value="id" show-clear filter placeholder="All projects" fluid @change="onProjectChange" /></label>
      <label>Well<Select v-model="wellId" :options="wellOptions" option-label="code" option-value="id" filter placeholder="Select well" fluid @change="loadComparison"><template #option="{ option }"><strong>{{ option.code }}</strong>&nbsp;— {{ option.name }}</template></Select></label>
      <div v-if="comparison"><span>Governing AFE</span><strong>{{ comparison.afe_code ?? 'Not configured' }}</strong><small>{{ comparison.afe_title }}</small></div>
    </section>

    <section v-if="comparison" class="control-kpis">
      <article><span>AFE budget</span><strong>${{ money(comparison.afe_budget) }}</strong><small>{{ Number(comparison.total_planned_days).toFixed(1) }} planned days</small></article>
      <article><span>AFE Cost Estimate</span><strong>${{ money(comparison.estimate_total) }}</strong><small>Priced AFE lines</small></article>
      <article><span>Daily Cost actual</span><strong class="primary">${{ money(comparison.cumulative_actual_cost) }}</strong><small>{{ comparison.days_elapsed }} entries logged</small></article>
      <article><span>Budget remaining</span><strong :class="Number(comparison.variance_to_budget) < 0 ? 'danger' : 'success'">${{ money(comparison.variance_to_budget) }}</strong><small>{{ budgetUsed.toFixed(1) }}% of budget used</small></article>
      <article><span>Estimate remaining</span><strong :class="Number(comparison.variance_to_estimate) < 0 ? 'danger' : 'success'">${{ money(comparison.variance_to_estimate) }}</strong><small>Estimate less actual</small></article>
    </section>

    <Tabs v-if="comparison" v-model:value="activeTab">
      <TabList><Tab value="date">Daily reconciliation</Tab><Tab value="section">By section</Tab><Tab value="activity">By activity</Tab><Tab value="phase">By phase</Tab></TabList>
      <TabPanels>
        <TabPanel value="date"><DataTable :value="comparison.by_date" paginator :rows="25" striped-rows show-gridlines class="bulk-grid-panel"><Column field="entry_date" header="Date" /><Column field="phase" header="Phase" /><Column field="hole_section_code" header="Section" /><Column field="activity_name" header="Activity" /><Column header="Daily actual"><template #body="{ data }">${{ money(data.daily_cost) }}</template></Column><Column header="Cumulative"><template #body="{ data }"><strong>${{ money(data.cumulative_cost) }}</strong></template></Column><Column header="Planned cumulative"><template #body="{ data }">{{ data.planned_cumulative == null ? '—' : `$${money(data.planned_cumulative)}` }}</template></Column></DataTable></TabPanel>
        <TabPanel value="section"><DataTable :value="comparison.by_section" striped-rows show-gridlines class="bulk-grid-panel"><Column field="label" header="Hole section" /><Column header="Planned estimate"><template #body="{ data }">{{ data.planned_cost == null ? '—' : `$${money(data.planned_cost)}` }}</template></Column><Column header="Actual"><template #body="{ data }">${{ money(data.total_cost) }}</template></Column><Column header="Variance"><template #body="{ data }"><strong :class="Number(data.variance ?? 0) < 0 ? 'danger' : 'success'">{{ data.variance == null ? '—' : `$${money(data.variance)}` }}</strong></template></Column></DataTable></TabPanel>
        <TabPanel value="activity"><DataTable :value="comparison.by_sub_activity" striped-rows show-gridlines class="bulk-grid-panel"><Column field="activity_name" header="Activity" /><Column field="label" header="Sub-activity" /><Column field="responsible_party" header="Responsible party" /><Column header="Operational charges"><template #body="{ data }">${{ money(data.services_cost) }}</template></Column><Column header="Quantity charges"><template #body="{ data }">${{ money(data.consumables_cost) }}</template></Column><Column header="Actual total"><template #body="{ data }"><strong>${{ money(data.total_cost) }}</strong></template></Column></DataTable></TabPanel>
        <TabPanel value="phase"><DataTable :value="comparison.by_phase" striped-rows show-gridlines class="bulk-grid-panel"><Column field="label" header="Phase" /><Column field="planned_days" header="Planned days" /><Column field="actual_days" header="Actual days" /><Column header="Actual total"><template #body="{ data }"><strong>${{ money(data.total_cost) }}</strong></template></Column></DataTable></TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
.control-selector { display: grid; grid-template-columns: repeat(3, minmax(200px, 1fr)); gap: 1rem; padding: 1rem; margin-bottom: 1rem; }
.control-selector label, .control-selector > div { display: grid; gap: .35rem; color: var(--text-color-secondary); font-size: .75rem; text-transform: uppercase; }
.control-selector strong { color: var(--text-color); font-size: 1rem; }
.control-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .8rem; margin-bottom: 1rem; }
.control-kpis article { display: grid; gap: .3rem; padding: 1rem; border: 1px solid var(--surface-border); border-radius: 10px; background: var(--surface-card); }
.control-kpis span { color: var(--text-color-secondary); font-size: .75rem; text-transform: uppercase; } .control-kpis strong { font-size: 1.25rem; } .control-kpis small { color: var(--text-color-secondary); }
.primary { color: var(--primary-color); } .success { color: #16a34a; } .danger { color: #dc2626; }
@media (max-width: 760px) { .control-selector { grid-template-columns: 1fr; } }
</style>
