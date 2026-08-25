<script setup lang="ts">
/** Configurable reports over the active Master Data → AFE → Daily Cost chain. */
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { AfeRecord, ProjectRecord, WellRecord } from '~/types/afe'
import type { GeneratedReport, ReportColumn, ReportFilters, ReportType } from '~/types/reporting'
import { downloadBlob } from '~/utils/download'
import { escapeHtml, formatMoneyCell, printDocument } from '~/utils/printDocument'

definePageMeta({ middleware: 'auth' })

const api = useReporting()
const afeApi = useAfe()
const projects = ref<ProjectRecord[]>([])
const wells = ref<WellRecord[]>([])
const afes = ref<AfeRecord[]>([])
const report = ref<GeneratedReport | null>(null)
const loading = ref(false)
const exporting = ref(false)
const error = ref<string | null>(null)

const reportOptions: { label: string, value: ReportType, description: string }[] = [
  { label: 'AFE Register', value: 'afe_register', description: 'AFE headers, budgets and priced estimate totals.' },
  { label: 'AFE Cost Estimate Detail', value: 'afe_cost_estimate', description: 'Every configured AFE line with its saved rate and estimated amount.' },
  { label: 'Daily Cost Register', value: 'daily_cost', description: 'Daily operational actuals, activities, phases and cumulative cost.' },
  { label: 'Cost Performance', value: 'cost_performance', description: 'AFE budget and estimate compared with Daily Cost actuals by well.' },
  { label: 'Well Activities & Accountability', value: 'well_activities', description: 'Configured well activities and actual costs by responsible party.' },
]

const filters = ref<ReportFilters>({ report_type: 'afe_register' })
const wellOptions = computed(() => filters.value.project_id
  ? wells.value.filter(well => well.project_id === filters.value.project_id)
  : wells.value)
const afeOptions = computed(() => afes.value.filter(afe =>
  (!filters.value.well_id || afe.well_id === filters.value.well_id)
  && (!filters.value.project_id || afe.project_id === filters.value.project_id),
))
const supportsDates = computed(() => ['daily_cost', 'cost_performance', 'well_activities'].includes(filters.value.report_type))
const selectedDescription = computed(() => reportOptions.find(item => item.value === filters.value.report_type)?.description ?? '')

function resetDependent(level: 'project' | 'well'): void {
  if (level === 'project') filters.value.well_id = undefined
  filters.value.afe_id = undefined
}

function displayValue(value: string | number | null, column: ReportColumn): string {
  if (value == null || value === '') return '—'
  if (column.format === 'money') return `$${formatMoneyCell(value)}`
  if (column.format === 'number' && typeof value === 'number') return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (column.format === 'date') return new Date(`${value}T00:00:00`).toLocaleDateString()
  return String(value)
}

function summaryValue(value: string | number | null, format: string): string {
  if (value == null) return '—'
  if (format === 'money') return `$${formatMoneyCell(value)}`
  return typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value)
}

async function generate(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    report.value = await api.generate(filters.value)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The report could not be generated.'
    report.value = null
  }
  finally { loading.value = false }
}

async function exportExcel(): Promise<void> {
  exporting.value = true
  error.value = null
  try {
    downloadBlob(await api.export(filters.value), `${filters.value.report_type.replaceAll('_', '-')}.xlsx`)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The report export failed.'
  }
  finally { exporting.value = false }
}

function printReport(): void {
  if (!report.value) return
  const detail = report.value
  const header = detail.columns.map(column => `<th>${escapeHtml(column.label)}</th>`).join('')
  const body = detail.rows.map(row => `<tr>${detail.columns.map(column => `<td class="${column.format === 'money' || column.format === 'number' ? 'num' : ''}">${escapeHtml(displayValue(row[column.key] ?? null, column))}</td>`).join('')}</tr>`).join('')
  const summary = detail.summaries.map(item => `<div><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(summaryValue(item.value, item.format))}</strong></div>`).join('')
  printDocument(detail.title, `
    <h1>${escapeHtml(detail.title.toUpperCase())}</h1>
    <p class="doc-subtitle">${escapeHtml(detail.description)}</p>
    <div class="meta-grid">${summary}</div>
    <table><thead><tr>${header}</tr></thead><tbody>${body || `<tr><td colspan="${detail.columns.length}">No records match the selected filters.</td></tr>`}</tbody></table>
    <p class="print-footer">Generated ${new Date(detail.generated_at).toLocaleString()} · Printed ${new Date().toLocaleString()}</p>
  `)
}

watch(() => filters.value.report_type, () => {
  if (!supportsDates.value) {
    filters.value.date_from = undefined
    filters.value.date_to = undefined
  }
})

onMounted(async () => {
  try {
    const [projectPage, wellPage, afePage] = await Promise.all([
      afeApi.listProjects(), afeApi.listWells(), afeApi.listAfes(),
    ])
    projects.value = projectPage.items.filter(item => item.is_active)
    wells.value = wellPage.items.filter(item => item.is_active)
    afes.value = afePage.items.filter(item => item.is_active)
    await generate()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Report reference data could not be loaded.'
  }
})
</script>

<template>
  <div class="reports-page">
    <PageHeader
      title="Reports"
      description="Generate live reports directly from Master Data, AFE, AFE Cost Estimates, Daily Cost and Well Activities."
    >
      <template #actions>
        <Button label="Print" icon="pi pi-print" outlined :disabled="!report" @click="printReport" />
        <Button label="Export Excel" icon="pi pi-file-excel" outlined :loading="exporting" :disabled="!report" @click="exportExcel" />
        <Button label="Generate" icon="pi pi-play" :loading="loading" @click="generate" />
      </template>
    </PageHeader>

    <Message v-if="error" severity="error" closable @close="error = null">{{ error }}</Message>

    <section class="report-config bulk-grid-panel">
      <label class="report-type">Report
        <Select v-model="filters.report_type" :options="reportOptions" option-label="label" option-value="value" fluid>
          <template #option="{ option }"><div><strong>{{ option.label }}</strong><small>{{ option.description }}</small></div></template>
        </Select>
        <small>{{ selectedDescription }}</small>
      </label>
      <label>Project<Select v-model="filters.project_id" :options="projects" option-label="code" option-value="id" show-clear filter placeholder="All projects" fluid @change="resetDependent('project')" /></label>
      <label>Well<Select v-model="filters.well_id" :options="wellOptions" option-label="code" option-value="id" show-clear filter placeholder="All wells" fluid @change="resetDependent('well')" /></label>
      <label>AFE<Select v-model="filters.afe_id" :options="afeOptions" option-label="code" option-value="id" show-clear filter placeholder="All AFEs" fluid /></label>
      <label v-if="supportsDates">From<InputText v-model="filters.date_from" type="date" fluid /></label>
      <label v-if="supportsDates">To<InputText v-model="filters.date_to" type="date" fluid /></label>
    </section>

    <section v-if="report" class="report-summary-grid">
      <article v-for="item in report.summaries" :key="item.key">
        <span>{{ item.label }}</span>
        <strong>{{ summaryValue(item.value, item.format) }}</strong>
      </article>
    </section>

    <section v-if="report" class="report-result">
      <header>
        <div><span class="eyebrow">Generated report</span><h2>{{ report.title }}</h2><p>{{ report.description }}</p></div>
        <Tag :value="`${report.rows.length} rows`" severity="info" />
      </header>
      <DataTable :value="report.rows" :loading="loading" paginator :rows="25" :rows-per-page-options="[10, 25, 50, 100]" striped-rows show-gridlines scrollable class="bulk-grid-panel">
        <Column v-for="column in report.columns" :key="column.key" :field="column.key" :header="column.label" :style="{ minWidth: column.format === 'money' ? '140px' : '120px' }">
          <template #body="{ data }">
            <Tag v-if="column.format === 'status'" :value="displayValue(data[column.key], column)" :severity="data[column.key] === 'submitted' ? 'success' : 'warn'" />
            <span v-else :class="{ 'report-number': column.format === 'money' || column.format === 'number' }">{{ displayValue(data[column.key], column) }}</span>
          </template>
        </Column>
        <template #empty>No records match the selected report filters.</template>
      </DataTable>
      <small class="generated-at">Generated {{ new Date(report.generated_at).toLocaleString() }}</small>
    </section>
  </div>
</template>

<style scoped>
.report-config { display: grid; grid-template-columns: minmax(240px, 1.4fr) repeat(5, minmax(150px, 1fr)); gap: .8rem; padding: 1rem; margin-bottom: 1rem; align-items: start; }
.report-config label { display: grid; gap: .35rem; font-size: .75rem; font-weight: 600; color: var(--text-color-secondary); text-transform: uppercase; }
.report-config small { text-transform: none; font-weight: 400; line-height: 1.35; }
.report-type :deep(.p-select-option > div) { display: grid; gap: .15rem; } .report-type :deep(.p-select-option small) { color: var(--text-color-secondary); }
.report-summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .8rem; margin-bottom: 1rem; }
.report-summary-grid article { display: grid; gap: .3rem; padding: 1rem; border: 1px solid var(--surface-border); border-radius: 10px; background: var(--surface-card); }
.report-summary-grid span { color: var(--text-color-secondary); font-size: .75rem; text-transform: uppercase; }
.report-summary-grid strong { font-size: 1.3rem; }
.report-result > header { display: flex; justify-content: space-between; align-items: start; gap: 1rem; margin: 1rem 0 .7rem; }
.report-result h2 { margin: .15rem 0; } .report-result p { margin: 0; color: var(--text-color-secondary); }
.report-number { display: block; text-align: right; font-variant-numeric: tabular-nums; }
.generated-at { display: block; margin-top: .5rem; color: var(--text-color-secondary); text-align: right; }
@media (max-width: 1100px) { .report-config { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .report-config { grid-template-columns: 1fr; } }
</style>
