<script setup lang="ts">
/**
 * AFE Cost Estimates — pricing the AFE, well scoped.
 *
 * The AFE page defines the scope: services, chemicals, additives, tangibles,
 * sections, phases, and quantities. This page grabs those AFE lines and lets
 * the user input the well-scoped unit rate for each of them. The saved rates
 * are the single source of unit rates for daily cost entry (which keeps its
 * per-line override for exceptional days).
 *
 * Export and Print produce a record-quality copy of the priced AFE.
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
import type { AfeCostEstimate, AfeCostEstimateGroupTotal, AfeCostEstimateLine } from '~/types/afeEstimates'
import type { AfeRecord, ProjectRecord, WellRecord } from '~/types/afe'
import type { MasterDataRecord } from '~/types/masterData'
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
const selectedWellId = ref<string>('')
const selectedAfeId = ref<string>('')

const estimate = ref<AfeCostEstimate | null>(null)

interface EditableEstimateLine extends AfeCostEstimateLine {
  _rate: number
  _vendorId: string | null
  _remarks: string
  _dirty: boolean
}
const rows = ref<EditableEstimateLine[]>([])

const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

const wellOptions = computed(() =>
  projectFilter.value ? wells.value.filter(w => w.project_id === projectFilter.value) : wells.value)

const dirtyCount = computed(() => rows.value.filter(row => row._dirty).length)

function lineAmount(row: EditableEstimateLine): number {
  return Number(row.quantity) * (Number(row._rate) || 0)
}
const estimatedTotal = computed(() => rows.value.reduce((sum, row) => sum + lineAmount(row), 0))
const servicesTotal = computed(() =>
  rows.value.filter(row => row.item_type === 'service').reduce((sum, row) => sum + lineAmount(row), 0))
const consumablesTotal = computed(() => estimatedTotal.value - servicesTotal.value)
const pricedCount = computed(() => rows.value.filter(row => Number(row._rate) > 0).length)

function groupTotals(dimension: 'section' | 'item_type' | 'cost_code'): AfeCostEstimateGroupTotal[] {
  const buckets = new Map<string, AfeCostEstimateGroupTotal>()
  for (const row of rows.value) {
    const key = dimension === 'section'
      ? (row.applies_to_all_sections ? 'All sections' : (row.hole_section_code ?? 'Unassigned'))
      : dimension === 'item_type'
        ? (row.item_type ?? 'other').replace(/_/g, ' ')
        : (row.cost_code ?? 'Unassigned')
    let bucket = buckets.get(key)
    if (!bucket) {
      bucket = { key, label: key, line_count: 0, estimated_total: 0 }
      buckets.set(key, bucket)
    }
    bucket.line_count += 1
    bucket.estimated_total = Number(bucket.estimated_total) + lineAmount(row)
  }
  return [...buckets.values()].sort((a, b) => Number(b.estimated_total) - Number(a.estimated_total))
}
const sectionTotals = computed(() => groupTotals('section'))
const itemTypeTotals = computed(() => groupTotals('item_type'))
const costCodeTotals = computed(() => groupTotals('cost_code'))

function money(value: string | number | null | undefined): string {
  return formatMoneyCell(value)
}

async function loadFoundation(): Promise<void> {
  const [projectPage, wellPage, vendorPage] = await Promise.all([
    afeApi.listProjects(),
    afeApi.listWells(),
    master.list('vendors'),
  ])
  projects.value = (projectPage.items || []).filter(p => p.is_active)
  wells.value = (wellPage.items || []).filter(w => w.is_active)
  vendors.value = (vendorPage.items || []).filter(v => v.is_active)
}

async function onWellChange(): Promise<void> {
  selectedAfeId.value = ''
  estimate.value = null
  rows.value = []
  afes.value = []
  if (!selectedWellId.value) return
  try {
    const page = await afeApi.listAfes(selectedWellId.value)
    afes.value = page.items || []
    // Prefer the governing (submitted, highest revision) AFE by default.
    const preferred = [...afes.value].sort((a, b) =>
      (b.status === 'submitted' ? 1 : 0) - (a.status === 'submitted' ? 1 : 0)
      || b.revision_number - a.revision_number)[0]
    if (preferred) {
      selectedAfeId.value = preferred.id
      await loadEstimate()
    }
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Could not load the well\u2019s AFEs.'
  }
}

async function loadEstimate(): Promise<void> {
  if (!selectedAfeId.value) return
  loading.value = true
  error.value = null
  try {
    estimate.value = await estimatesApi.get(selectedAfeId.value)
    rows.value = estimate.value.lines.map(line => ({
      ...line,
      _rate: Number(line.unit_rate) || 0,
      _vendorId: line.vendor_id,
      _remarks: line.remarks ?? '',
      _dirty: false,
    }))
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Could not load the AFE cost estimate.'
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
    const payload = rows.value.map(row => ({
      afe_line_id: row.afe_line_id,
      unit_rate: Number(row._rate) || 0,
      vendor_id: row._vendorId || null,
      remarks: row._remarks.trim() || null,
    }))
    estimate.value = await estimatesApi.saveRates(selectedAfeId.value, payload)
    rows.value = estimate.value.lines.map(line => ({
      ...line,
      _rate: Number(line.unit_rate) || 0,
      _vendorId: line.vendor_id,
      _remarks: line.remarks ?? '',
      _dirty: false,
    }))
    success.value = `Unit rates saved for AFE ${estimate.value.afe_code}. Daily cost entries now read these rates.`
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The unit rates could not be saved.'
  }
  finally { saving.value = false }
}

async function exportExcel(): Promise<void> {
  if (!selectedAfeId.value) return
  try {
    const blob = await estimatesApi.export(selectedAfeId.value)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `afe-cost-estimate-${estimate.value?.afe_code ?? 'export'}.xlsx`
    anchor.click()
    URL.revokeObjectURL(url)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The export failed.'
  }
}

function printEstimate(): void {
  const detail = estimate.value
  if (!detail) return
  const meta = [
    ['Project', `${detail.project_code ?? ''} — ${detail.project_name ?? ''}`],
    ['Well', `${detail.well_code ?? ''} — ${detail.well_name ?? ''}`],
    ['Rig', detail.rig_name ?? '—'],
    ['AFE', `${detail.afe_code} (rev ${detail.revision_number})`],
    ['Title', detail.afe_title],
    ['Status', detail.afe_status],
    ['Planned days', String(Number(detail.total_planned_days))],
  ]
  const metaHtml = meta
    .map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join('')
  const lineRows = rows.value.map(row => `
    <tr>
      <td class="num">${row.line_number}</td>
      <td>${escapeHtml(row.catalog_item_code)}<br><small>${escapeHtml(row.catalog_item_name)}</small></td>
      <td>${escapeHtml((row.item_type ?? '').replace(/_/g, ' '))}</td>
      <td>${escapeHtml(row.cost_code ?? '')}</td>
      <td>${escapeHtml(row.applies_to_all_sections ? 'All sections' : (row.hole_section_code ?? '—'))}</td>
      <td>${escapeHtml(row.rate_basis.replace(/_/g, ' '))}</td>
      <td class="num">${Number(row.quantity)}</td>
      <td>${escapeHtml(row.unit_code ?? '')}</td>
      <td class="num">${money(row._rate)}</td>
      <td class="num">${money(lineAmount(row))}</td>
    </tr>`).join('')
  const summaryTable = (title: string, totals: AfeCostEstimateGroupTotal[]): string => `
    <h2>${escapeHtml(title)}</h2>
    <table><thead><tr><th>Group</th><th class="num">Lines</th><th class="num">Estimated total</th></tr></thead>
    <tbody>${totals.map(t => `<tr><td>${escapeHtml(t.label)}</td><td class="num">${t.line_count}</td><td class="num">${money(t.estimated_total)}</td></tr>`).join('')}</tbody></table>`
  printDocument(`AFE Cost Estimate ${detail.afe_code}`, `
    <h1>AFE COST ESTIMATE</h1>
    <p class="doc-subtitle">Well-scoped unit rates priced against the authorised AFE scope.</p>
    <div class="meta-grid">${metaHtml}</div>
    <h2>Priced AFE lines</h2>
    <table>
      <thead><tr><th class="num">#</th><th>Item</th><th>Type</th><th>Cost code</th><th>Section</th><th>Rate basis</th><th class="num">Qty</th><th>Unit</th><th class="num">Unit rate</th><th class="num">Estimated amount</th></tr></thead>
      <tbody>${lineRows}
        <tr class="total-row"><td colspan="9">Estimated total</td><td class="num">${money(estimatedTotal.value)}</td></tr>
      </tbody>
    </table>
    ${summaryTable('Totals by hole section', sectionTotals.value)}
    ${summaryTable('Totals by item type', itemTypeTotals.value)}
    ${summaryTable('Totals by cost code', costCodeTotals.value)}
    <div class="signatures"><div>Prepared by</div><div>Reviewed by</div><div>Approved by</div></div>
    <p class="print-footer">Printed ${new Date().toLocaleString()} — AFE Cost Estimates, well scoped.</p>
  `)
}

onMounted(() => {
  void loadFoundation().catch((caught: unknown) => {
    error.value = caught instanceof Error ? caught.message : 'Load failed'
  })
})
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="AFE Cost Estimates"
      description="Price the AFE. Every line added on the AFE page — services, chemicals, additives, tangibles — appears here for its well-scoped unit rate. Daily cost entries read these rates as their single source (a per-day override remains available at entry time)."
    >
      <template #actions>
        <Button label="Print" icon="pi pi-print" outlined :disabled="!estimate" @click="printEstimate" />
        <Button label="Export Excel" icon="pi pi-file-excel" outlined :disabled="!estimate" @click="exportExcel" />
        <Button
          :label="dirtyCount ? `Save rates (${dirtyCount})` : 'Save rates'"
          icon="pi pi-save" :loading="saving" :disabled="!rows.length" @click="saveRates"
        />
      </template>
    </PageHeader>

    <Message v-if="success" severity="success" :closable="true" @close="success = null">{{ success }}</Message>
    <Message v-if="error" severity="error" :closable="true" @close="error = null">{{ error }}</Message>

    <section class="est-selector-bar bulk-grid-panel">
      <div class="selector-field">
        <label>Project</label>
        <Select
          v-model="projectFilter" :options="projects" option-label="code" option-value="id"
          placeholder="All projects" show-clear filter style="min-width: 180px"
        />
      </div>
      <div class="selector-field">
        <label>Well</label>
        <Select
          v-model="selectedWellId" :options="wellOptions" option-label="code" option-value="id"
          placeholder="Select well" filter style="min-width: 220px" @change="onWellChange"
        >
          <template #option="{ option }">
            <strong>{{ option.code }}</strong>&nbsp;— {{ option.name }}
          </template>
        </Select>
      </div>
      <div class="selector-field">
        <label>AFE</label>
        <Select
          v-model="selectedAfeId" :options="afes" option-value="id" placeholder="Select AFE"
          style="min-width: 260px" :disabled="!afes.length" @change="loadEstimate"
        >
          <template #option="{ option }">
            <strong>{{ option.code }}</strong>&nbsp;— {{ option.title }}&nbsp;
            <Tag :value="option.status" :severity="option.status === 'submitted' ? 'success' : 'warn'" />
          </template>
          <template #value="{ value }">
            <span v-if="value">{{ afes.find(a => a.id === value)?.code }} — {{ afes.find(a => a.id === value)?.title }}</span>
            <span v-else>Select AFE</span>
          </template>
        </Select>
      </div>
      <div v-if="estimate" class="selector-field">
        <label>Status</label>
        <div class="afe-status-box">
          <Tag :value="estimate.afe_status" :severity="estimate.afe_status === 'submitted' ? 'success' : 'warn'" />
          <Tag
            :value="`${pricedCount}/${rows.length} lines priced`"
            :severity="pricedCount === rows.length && rows.length > 0 ? 'success' : 'warn'"
          />
        </div>
      </div>
    </section>

    <Message v-if="selectedWellId && !afes.length" severity="warn" :closable="false">
      This well has no AFE yet. Create the AFE and add its lines on the
      <NuxtLink to="/afe">AFE page</NuxtLink> first — the cost estimate prices exactly what the AFE scopes.
    </Message>
    <Message v-else-if="estimate && !rows.length" severity="warn" :closable="false">
      AFE {{ estimate.afe_code }} has no lines yet. Add services, chemicals, and additives on the
      <NuxtLink to="/afe">AFE page</NuxtLink>; they appear here automatically for pricing.
    </Message>

    <section v-if="estimate" class="est-kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">AFE Scope</span>
        <span class="kpi-value">{{ rows.length }} lines</span>
        <small class="kpi-sub">Planned days: {{ Number(estimate.total_planned_days).toFixed(1) }}</small>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Estimated Total</span>
        <span class="kpi-value text-primary">${{ money(estimatedTotal) }}</span>
        <small class="kpi-sub">Services ${{ money(servicesTotal) }} · Consumables ${{ money(consumablesTotal) }}</small>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Pricing Progress</span>
        <span class="kpi-value">{{ pricedCount }}/{{ rows.length }}</span>
        <small class="kpi-sub">{{ rows.length - pricedCount }} line(s) still without a unit rate</small>
      </div>
    </section>

    <DataTable
      v-if="rows.length"
      :value="rows" :loading="loading" data-key="afe_line_id"
      paginator :rows="50" striped-rows show-gridlines scrollable class="bulk-grid-panel"
    >
      <Column field="line_number" header="#" :style="{ width: '52px' }" />
      <Column header="Item" style="min-width: 220px">
        <template #body="{ data }">
          <strong>{{ data.catalog_item_code }}</strong><br>
          <small>{{ data.catalog_item_name }}</small>
        </template>
      </Column>
      <Column header="Type">
        <template #body="{ data }">
          <Tag :value="(data.item_type || 'other').replace('_', ' ')" severity="secondary" />
        </template>
      </Column>
      <Column field="cost_code" header="Cost code" />
      <Column header="Section">
        <template #body="{ data }">{{ data.hole_section_code || '—' }}</template>
      </Column>
      <Column header="Rate basis">
        <template #body="{ data }">{{ data.rate_basis.replace('_', ' ') }}</template>
      </Column>
      <Column header="Quantity">
        <template #body="{ data }">{{ Number(data.quantity) }}</template>
      </Column>
      <Column field="unit_code" header="Unit" />
      <Column header="Unit rate" style="min-width: 150px">
        <template #body="{ data }">
          <InputNumber
            v-model="data._rate" :min="0" :max-fraction-digits="4" mode="decimal"
            placeholder="0.00" fluid @input="mark(data)"
          />
        </template>
      </Column>
      <Column header="Estimated amount">
        <template #body="{ data }">
          <strong>${{ money(lineAmount(data)) }}</strong>
        </template>
      </Column>
      <Column header="Vendor" style="min-width: 170px">
        <template #body="{ data }">
          <Select
            v-model="data._vendorId" :options="vendors" option-label="name" option-value="id"
            show-clear filter placeholder="Optional" fluid @change="mark(data)"
          />
        </template>
      </Column>
      <Column header="Remarks" style="min-width: 170px">
        <template #body="{ data }">
          <InputText v-model="data._remarks" placeholder="Contract ref, T&Cs…" fluid @input="mark(data)" />
        </template>
      </Column>
    </DataTable>

    <section v-if="rows.length" class="est-summary-grid">
      <div class="summary-panel bulk-grid-panel">
        <h3>Totals by hole section</h3>
        <table class="summary-table">
          <tbody>
            <tr v-for="total in sectionTotals" :key="total.key">
              <td>{{ total.label }}</td>
              <td class="num">{{ total.line_count }}</td>
              <td class="num">${{ money(total.estimated_total) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="summary-panel bulk-grid-panel">
        <h3>Totals by item type</h3>
        <table class="summary-table">
          <tbody>
            <tr v-for="total in itemTypeTotals" :key="total.key">
              <td>{{ total.label }}</td>
              <td class="num">{{ total.line_count }}</td>
              <td class="num">${{ money(total.estimated_total) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="summary-panel bulk-grid-panel">
        <h3>Totals by cost code</h3>
        <table class="summary-table">
          <tbody>
            <tr v-for="total in costCodeTotals" :key="total.key">
              <td>{{ total.label }}</td>
              <td class="num">{{ total.line_count }}</td>
              <td class="num">${{ money(total.estimated_total) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.est-selector-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  align-items: flex-end;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}
.selector-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.selector-field label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-color-secondary, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.afe-status-box {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.est-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 0.9rem;
  margin-bottom: 1rem;
}
.kpi-card {
  background: var(--surface-card, #fff);
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 10px;
  padding: 0.9rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.kpi-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-color-secondary, #64748b);
}
.kpi-value {
  font-size: 1.35rem;
  font-weight: 700;
}
.kpi-sub {
  color: var(--text-color-secondary, #64748b);
}
.text-primary { color: var(--primary-color, #0f766e); }
.text-success { color: #16a34a; }
.text-danger { color: #dc2626; }
.est-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 0.9rem;
  margin-top: 1rem;
}
.summary-panel {
  padding: 1rem 1.2rem;
}
.summary-panel h3 {
  margin: 0 0 0.6rem;
  font-size: 0.95rem;
}
.summary-table {
  width: 100%;
  border-collapse: collapse;
}
.summary-table td {
  padding: 0.3rem 0.2rem;
  border-bottom: 1px solid var(--surface-border, #e2e8f0);
  font-size: 0.88rem;
}
.summary-table td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
