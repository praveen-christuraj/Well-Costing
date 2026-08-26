<script setup lang="ts">
/**
 * Prices submitted AFE scope lines. AFE Lines deliberately contains scope only;
 * this page is the single place where the current estimated rate is configured.
 */
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { AfeRecord, ProjectRecord, WellRecord } from '~/types/afe'
import type { AfeCostEstimate, AfeCostEstimateGroupTotal, AfeCostEstimateLine } from '~/types/afeEstimates'
import type { MasterDataRecord } from '~/types/masterData'
import { downloadBlob } from '~/utils/download'
import { escapeHtml, formatMoneyCell, printDocument } from '~/utils/printDocument'

definePageMeta({ middleware: 'auth' })

const afeApi = useAfe()
const estimatesApi = useAfeEstimates()
const master = useMasterData()

const projects = ref<ProjectRecord[]>([])
const wells = ref<WellRecord[]>([])
const afes = ref<AfeRecord[]>([])
const vendors = ref<MasterDataRecord[]>([])
const projectFilter = ref<string | null>(null)
const selectedWellId = ref('')
const selectedAfeId = ref('')
const estimate = ref<AfeCostEstimate | null>(null)

interface EditableEstimateLine extends AfeCostEstimateLine {
  _estimatedRate: number
  _vendorId: string | null
  _remarks: string
  _dirty: boolean
}

const rows = ref<EditableEstimateLine[]>([])
const loading = ref(false)
const saving = ref(false)
const exporting = ref(false)
const printing = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

const wellOptions = computed(() => projectFilter.value
  ? wells.value.filter(well => well.project_id === projectFilter.value)
  : wells.value)
const dirtyCount = computed(() => rows.value.filter(row => row._dirty).length)
const pricedCount = computed(() => rows.value.filter(row => Number(row._estimatedRate) > 0).length)

/**
 * Current AFE lines are scope-only. A saved rate is therefore the line's
 * estimated total. Historic lines with a positive planned quantity remain
 * readable with their quantity-based estimate.
 */
function estimateMultiplier(row: AfeCostEstimateLine): number {
  const quantity = Number(row.quantity)
  return Number.isFinite(quantity) && quantity > 0 ? quantity : 1
}

function lineAmount(row: EditableEstimateLine): number {
  return estimateMultiplier(row) * (Number(row._estimatedRate) || 0)
}

const estimatedTotal = computed(() => rows.value.reduce((sum, row) => sum + lineAmount(row), 0))
const varianceToBudget = computed(() => Number(estimate.value?.budget_amount ?? 0) - estimatedTotal.value)

function classification(row: AfeCostEstimateLine): string {
  const primary = row.primary_category_name || row.primary_category_code
  const secondary = row.secondary_category_name || row.secondary_category_code
  if (primary && secondary) return `${primary} / ${secondary}`
  return secondary || primary || row.catalog_item_name || row.catalog_item_code || 'Unassigned'
}

function groupTotals(dimension: 'section' | 'primary' | 'secondary' | 'cost_code'): AfeCostEstimateGroupTotal[] {
  const buckets = new Map<string, AfeCostEstimateGroupTotal>()
  for (const row of rows.value) {
    const key = dimension === 'section'
      ? (row.applies_to_all_sections ? 'All sections' : (row.hole_section_code ?? 'Unassigned'))
      : dimension === 'primary'
        ? (row.primary_category_name || row.primary_category_code || 'Unassigned')
        : dimension === 'secondary'
          ? (row.secondary_category_name || row.secondary_category_code || 'Unassigned')
          : (row.cost_code ?? 'Unassigned')
    const bucket = buckets.get(key) ?? { key, label: key, line_count: 0, estimated_total: 0 }
    bucket.line_count += 1
    bucket.estimated_total = Number(bucket.estimated_total) + lineAmount(row)
    buckets.set(key, bucket)
  }
  return [...buckets.values()].sort((a, b) => Number(b.estimated_total) - Number(a.estimated_total))
}

const sectionTotals = computed(() => groupTotals('section'))
const primaryTotals = computed(() => groupTotals('primary'))
const secondaryTotals = computed(() => groupTotals('secondary'))
const costCodeTotals = computed(() => groupTotals('cost_code'))

function money(value: string | number | null | undefined): string {
  return formatMoneyCell(value)
}

function setRows(detail: AfeCostEstimate): void {
  rows.value = detail.lines.map(line => ({
    ...line,
    _estimatedRate: Number(line.unit_rate) || 0,
    _vendorId: line.vendor_id,
    _remarks: line.remarks ?? '',
    _dirty: false,
  }))
}

async function loadFoundation(): Promise<void> {
  const [projectPage, wellPage, vendorPage] = await Promise.all([
    afeApi.listProjects(),
    afeApi.listWells(),
    master.list('vendors'),
  ])
  projects.value = (projectPage.items || []).filter(item => item.is_active)
  wells.value = (wellPage.items || []).filter(item => item.is_active)
  vendors.value = (vendorPage.items || []).filter(item => item.is_active)
}

async function onWellChange(): Promise<void> {
  selectedAfeId.value = ''
  estimate.value = null
  rows.value = []
  afes.value = []
  error.value = null
  success.value = null
  if (!selectedWellId.value) return

  try {
    // Pricing is available only after the AFE scope is submitted. The API also
    // enforces this gate, so a stale URL cannot open a draft AFE for pricing.
    const page = await afeApi.listAfes(selectedWellId.value, 'submitted')
    afes.value = page.items || []
    const preferred = [...afes.value].sort((a, b) => b.revision_number - a.revision_number)[0]
    if (preferred) {
      selectedAfeId.value = preferred.id
      await loadEstimate()
    }
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Could not load the well’s submitted AFEs.'
  }
}

async function loadEstimate(): Promise<void> {
  if (!selectedAfeId.value) return
  loading.value = true
  error.value = null
  try {
    estimate.value = await estimatesApi.get(selectedAfeId.value)
    setRows(estimate.value)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Could not load the AFE Cost Estimate.'
    estimate.value = null
    rows.value = []
  }
  finally { loading.value = false }
}

function mark(row: EditableEstimateLine): void {
  row._dirty = true
}

async function saveRates(): Promise<void> {
  if (!selectedAfeId.value || !rows.value.length) return
  saving.value = true
  error.value = null
  success.value = null
  try {
    estimate.value = await estimatesApi.saveRates(selectedAfeId.value, rows.value.map(row => ({
      afe_line_id: row.afe_line_id,
      // The released Cost Estimate page has one current estimate rate. It is
      // mirrored to operating_rate for Daily Cost compatibility.
      unit_rate: Number(row._estimatedRate) || 0,
      operating_rate: Number(row._estimatedRate) || 0,
      // Daily operational charges still multiply by the entered fraction of a
      // day. Fixed/section/service charges do not.
      multiply_by_input: row.rate_basis === 'daily',
      vendor_id: row._vendorId || null,
      remarks: row._remarks.trim() || null,
    })))
    setRows(estimate.value)
    success.value = `Estimate rates saved for submitted AFE ${estimate.value.afe_code}. Daily Cost now reads these line rates.`
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The estimate rates could not be saved.'
  }
  finally { saving.value = false }
}

async function exportExcel(): Promise<void> {
  if (!selectedAfeId.value) return
  exporting.value = true
  error.value = null
  try {
    downloadBlob(
      await estimatesApi.export(selectedAfeId.value),
      `afe-cost-estimate-${estimate.value?.afe_code ?? 'export'}.xlsx`,
    )
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The export failed.'
  }
  finally { exporting.value = false }
}

function summaryTable(title: string, totals: AfeCostEstimateGroupTotal[]): string {
  return `<h2>${escapeHtml(title)}</h2><table><thead><tr><th>Group</th><th class="num">Lines</th><th class="num">Estimated total</th></tr></thead><tbody>${totals.map(total => `<tr><td>${escapeHtml(total.label)}</td><td class="num">${total.line_count}</td><td class="num">${money(total.estimated_total)}</td></tr>`).join('')}</tbody></table>`
}

async function printEstimate(): Promise<void> {
  const detail = estimate.value
  if (!detail) return
  printing.value = true
  error.value = null
  try {
    // Browser print has no server request of its own, so record it explicitly
    // before opening the current-page document.
    await estimatesApi.recordPrint(detail.afe_id)
    const meta = [
      ['Project', `${detail.project_code ?? ''} — ${detail.project_name ?? ''}`],
      ['Well', `${detail.well_code ?? ''} — ${detail.well_name ?? ''}`],
      ['Rig', detail.rig_name ?? '—'],
      ['AFE', `${detail.afe_code} (rev ${detail.revision_number})`],
      ['Title', detail.afe_title],
      ['Status', detail.afe_status],
      ['AFE budget', money(detail.budget_amount)],
      ['Estimated total', money(estimatedTotal.value)],
    ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('')
    const lineRows = rows.value.map(row => `<tr>
      <td class="num">${row.line_number}</td><td>${escapeHtml(classification(row))}</td>
      <td>${escapeHtml(row.cost_code ?? '')}</td><td>${escapeHtml(row.applies_to_all_sections ? 'All sections' : (row.hole_section_code ?? '—'))}</td>
      <td>${escapeHtml(row.rate_basis.replaceAll('_', ' '))}</td><td class="num">${money(row._estimatedRate)}</td><td class="num">${money(lineAmount(row))}</td>
    </tr>`).join('')
    printDocument(`AFE Cost Estimate ${detail.afe_code}`, `
      <h1>AFE COST ESTIMATE</h1>
      <p class="doc-subtitle">Current submitted AFE scope and its saved estimate rates. Consumable quantities are recorded only in Daily Cost.</p>
      <div class="meta-grid">${meta}</div>
      <h2>Priced AFE lines</h2>
      <table><thead><tr><th class="num">#</th><th>Classification</th><th>Cost code</th><th>Section</th><th>Costing method</th><th class="num">Estimated total rate</th><th class="num">Estimated amount</th></tr></thead>
        <tbody>${lineRows}<tr class="total-row"><td colspan="6">Estimated total</td><td class="num">${money(estimatedTotal.value)}</td></tr></tbody></table>
      ${summaryTable('Totals by primary category', primaryTotals.value)}
      ${summaryTable('Totals by secondary category', secondaryTotals.value)}
      ${summaryTable('Totals by hole section', sectionTotals.value)}
      ${summaryTable('Totals by cost code', costCodeTotals.value)}
      <div class="signatures"><div>Prepared by</div><div>Reviewed by</div><div>Approved by</div></div>
      <p class="print-footer">Printed ${new Date().toLocaleString()} — source: current AFE Cost Estimates module.</p>
    `)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE Cost Estimate could not be printed.'
  }
  finally { printing.value = false }
}

onMounted(() => void loadFoundation().catch((caught: unknown) => {
  error.value = caught instanceof Error ? caught.message : 'Could not load reference data.'
}))
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="AFE Cost Estimates"
      description="Configure one estimated rate for each submitted AFE scope line. Actual consumable quantities are entered only on Daily Cost."
    >
      <template #actions>
        <Button label="Print" icon="pi pi-print" outlined :loading="printing" :disabled="!estimate" @click="printEstimate" />
        <Button label="Export Excel" icon="pi pi-file-excel" outlined :loading="exporting" :disabled="!estimate" @click="exportExcel" />
        <Button :label="dirtyCount ? `Save rates (${dirtyCount})` : 'Save rates'" icon="pi pi-save" :loading="saving" :disabled="!rows.length" @click="saveRates" />
      </template>
    </PageHeader>

    <Message v-if="success" severity="success" closable @close="success = null">{{ success }}</Message>
    <Message v-if="error" severity="error" closable @close="error = null">{{ error }}</Message>

    <section class="est-selector-bar bulk-grid-panel">
      <label>Project<Select v-model="projectFilter" :options="projects" option-label="code" option-value="id" placeholder="All projects" show-clear filter /></label>
      <label>Well<Select v-model="selectedWellId" :options="wellOptions" option-label="code" option-value="id" placeholder="Select well" filter @change="onWellChange"><template #option="{ option }"><strong>{{ option.code }}</strong>&nbsp;— {{ option.name }}</template></Select></label>
      <label>Submitted AFE<Select v-model="selectedAfeId" :options="afes" option-value="id" :disabled="!afes.length" placeholder="Select submitted AFE" @change="loadEstimate"><template #option="{ option }"><strong>{{ option.code }}</strong>&nbsp;— {{ option.title }}</template><template #value="{ value }"><span v-if="value">{{ afes.find(item => item.id === value)?.code }} — {{ afes.find(item => item.id === value)?.title }}</span><span v-else>Select submitted AFE</span></template></Select></label>
      <div v-if="estimate" class="selector-status"><span>Status</span><div><Tag :value="estimate.afe_status" severity="success" /><Tag :value="`${pricedCount}/${rows.length} lines priced`" :severity="pricedCount === rows.length && rows.length > 0 ? 'success' : 'warn'" /></div></div>
    </section>

    <Message v-if="selectedWellId && !afes.length" severity="warn" :closable="false">This well has no submitted AFE yet. Complete and submit its scope on the <NuxtLink to="/afe">AFE page</NuxtLink> before entering estimate rates.</Message>
    <Message v-else-if="estimate && !rows.length" severity="warn" :closable="false">Submitted AFE {{ estimate.afe_code }} has no scope lines. Add lines on the <NuxtLink to="/afe">AFE page</NuxtLink>, then submit it again.</Message>

    <section v-if="estimate" class="est-kpi-grid">
      <article><span>Submitted scope</span><strong>{{ rows.length }} lines</strong><small>AFE rev {{ estimate.revision_number }}</small></article>
      <article><span>Estimated total</span><strong class="text-primary">${{ money(estimatedTotal) }}</strong><small>Saved estimate rates</small></article>
      <article><span>Variance to AFE budget</span><strong :class="varianceToBudget < 0 ? 'text-danger' : 'text-success'">${{ money(varianceToBudget) }}</strong><small>Budget ${{ money(estimate.budget_amount) }}</small></article>
      <article><span>Pricing progress</span><strong>{{ pricedCount }}/{{ rows.length }}</strong><small>{{ rows.length - pricedCount }} line(s) without a rate</small></article>
    </section>

    <DataTable v-if="rows.length" :value="rows" :loading="loading" data-key="afe_line_id" paginator :rows="50" striped-rows show-gridlines scrollable scroll-height="calc(100vh - 350px)" class="bulk-grid-panel estimate-grid">
      <Column field="line_number" header="#" style="width: 52px" />
      <Column header="Classification" style="min-width: 220px"><template #body="{ data }"><div class="classification-cell"><strong>{{ data.primary_category_name || data.primary_category_code || '—' }}</strong><span>{{ data.secondary_category_name || data.secondary_category_code || data.catalog_item_name || '—' }}</span></div></template></Column>
      <Column field="cost_code" header="Cost code" style="min-width: 130px" />
      <Column header="Scope" style="min-width: 130px"><template #body="{ data }">{{ data.applies_to_all_sections ? 'All sections' : (data.hole_section_code || '—') }}</template></Column>
      <Column header="Method" style="min-width: 125px"><template #body="{ data }"><Tag :value="data.rate_basis.replaceAll('_', ' ')" severity="info" /></template></Column>
      <Column header="Estimated total rate" style="min-width: 155px"><template #body="{ data }"><InputNumber v-model="data._estimatedRate" :min="0" :max-fraction-digits="4" prefix="$ " fluid @input="mark(data)" /></template></Column>
      <Column header="Estimated amount" style="min-width: 145px"><template #body="{ data }"><strong>${{ money(lineAmount(data)) }}</strong></template></Column>
      <Column header="Vendor" style="min-width: 165px"><template #body="{ data }"><Select v-model="data._vendorId" :options="vendors" option-label="name" option-value="id" show-clear filter placeholder="Optional" fluid @change="mark(data)" /></template></Column>
      <Column header="Remarks" style="min-width: 170px"><template #body="{ data }"><InputText v-model="data._remarks" placeholder="Contract reference…" fluid @input="mark(data)" /></template></Column>
    </DataTable>

    <section v-if="rows.length" class="est-summary-grid">
      <article
        v-for="summary in [
          { title: 'By primary category', values: primaryTotals },
          { title: 'By secondary category', values: secondaryTotals },
          { title: 'By hole section', values: sectionTotals },
          { title: 'By cost code', values: costCodeTotals },
        ]"
        :key="summary.title"
        class="bulk-grid-panel"
      >
        <h3>{{ summary.title }}</h3>
        <table><tbody><tr v-for="total in summary.values" :key="total.key"><td>{{ total.label }}</td><td>{{ total.line_count }}</td><td>${{ money(total.estimated_total) }}</td></tr></tbody></table>
      </article>
    </section>
  </div>
</template>

<style scoped>
.est-selector-bar { display: flex; flex-wrap: wrap; gap: .8rem 1rem; align-items: end; padding: .8rem 1rem; margin-bottom: .75rem; }
.est-selector-bar > label, .selector-status { display: grid; gap: .25rem; min-width: 185px; font-size: .74rem; font-weight: 600; color: var(--text-color-secondary); text-transform: uppercase; letter-spacing: .04em; }
.selector-status > div { display: flex; gap: .4rem; min-height: 34px; align-items: center; }
.est-kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr)); gap: .7rem; margin-bottom: .75rem; }
.est-kpi-grid article { background: var(--surface-card); border: 1px solid var(--surface-border); border-radius: 8px; padding: .7rem .85rem; display: grid; gap: .2rem; }
.est-kpi-grid span { font-size: .7rem; text-transform: uppercase; color: var(--text-color-secondary); }
.est-kpi-grid strong { font-size: 1.15rem; }
.est-kpi-grid small { color: var(--text-color-secondary); font-size: .76rem; }
.text-primary { color: var(--primary-color); } .text-success { color: #16a34a; } .text-danger { color: #dc2626; }
.classification-cell { display: grid; gap: .08rem; line-height: 1.2; }
.classification-cell span { color: var(--text-color-secondary); font-size: .78rem; }
.estimate-grid :deep(.p-datatable-thead > tr > th), .estimate-grid :deep(.p-datatable-tbody > tr > td) { padding: .32rem .4rem; font-size: .8rem; }
.estimate-grid :deep(.p-select-label), .estimate-grid :deep(.p-inputnumber-input), .estimate-grid :deep(.p-inputtext) { font-size: .8rem; padding-block: .34rem; }
.est-summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: .7rem; margin-top: .75rem; }
.est-summary-grid article { padding: .75rem .9rem; }
.est-summary-grid h3 { margin: 0 0 .45rem; font-size: .88rem; }
.est-summary-grid table { width: 100%; border-collapse: collapse; }
.est-summary-grid td { padding: .25rem .15rem; border-bottom: 1px solid var(--surface-border); font-size: .8rem; }
.est-summary-grid td:nth-child(n+2) { text-align: right; font-variant-numeric: tabular-nums; }
@media (max-width: 720px) { .est-selector-bar > label { min-width: 100%; } }
</style>
