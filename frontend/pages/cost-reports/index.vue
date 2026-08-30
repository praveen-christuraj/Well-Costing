<script setup lang="ts">
/**
 * Cost Reports — the daily costs incurred, drilled through.
 *
 * The user picks a drill-through (date, hole section, phase, well activity,
 * well sub activity, service, charge category, consumable category, tangible or
 * the overall well), narrows it by rig / well / date range and whether draft
 * days count, then clicks any row to see the cost lines behind it. The Depth vs
 * Cost graph is shown for the selected well, and the report or its detail lines
 * can be exported as XLSX/CSV and printed.
 */
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import DatePicker from 'primevue/datepicker'
import Message from 'primevue/message'
import Select from 'primevue/select'
import PageHeader from '~/components/design-system/PageHeader.vue'
import DepthCostChart from '~/components/daily-cost/DepthCostChart.vue'
import { formatDateLabel, formatMoney, formatQuantity, toDate, todayIso } from '~/utils/dailyCost'
import {
  CONSUMABLE_LABELS,
  type ConsumableCategory,
  type CostReport,
  type DepthCostPoint,
  type ReportDimension,
  type ReportDimensionOption,
  type ReportLine,
  type ReportLineBundle,
} from '~/types/dailyCost'
import type { GridSelectOption } from '~/types/grid'

definePageMeta({ middleware: 'auth' })

const api = useApi()

interface RigDropdown { id: number, rig_code: string, rig_name: string, display_name: string }
interface WellRecord { id: number, rig_id: number, well_code: string, well_name: string }
interface DepthCostResponse {
  well_code: string
  depth_unit: string
  points: DepthCostPoint[]
  total_estimated: string
  total_actual: string
  unattributed_actual: string
  notes: string[]
}

const rigs = ref<RigDropdown[]>([])
const wells = ref<WellRecord[]>([])
const dimensions = ref<ReportDimensionOption[]>([])

const dimension = ref<ReportDimension>('section')
const selectedRigId = ref<number | null>(null)
const selectedWellId = ref<number | null>(null)
const fromDate = ref<Date | null>(null)
const toDateValue = ref<Date | null>(null)
const fromDateIso = computed(() => (fromDate.value ? todayIso(fromDate.value) : null))
const toDateIso = computed(() => (toDateValue.value ? todayIso(toDateValue.value) : null))
const includeDraft = ref(true)

const report = ref<CostReport | null>(null)
const loading = ref(false)
const actionError = ref<string | null>(null)

const drillKey = ref<string | null>(null)
const drillLabel = ref<string>('')
const drill = ref<ReportLineBundle | null>(null)
const drillLoading = ref(false)

const depthSeries = ref<DepthCostResponse | null>(null)

const dimensionOptions = computed<GridSelectOption[]>(() =>
  dimensions.value.map(item => ({ label: item.title, value: item.dimension })),
)
const wellOptions = computed<GridSelectOption[]>(() =>
  (selectedRigId.value == null
    ? wells.value
    : wells.value.filter(well => well.rig_id === selectedRigId.value)
  ).map(well => ({ label: `${well.well_code} - ${well.well_name}`, value: well.id })),
)
const selectedWell = computed(() => wells.value.find(well => well.id === selectedWellId.value) ?? null)

/** Filters as one query string, shared by the report, the lines and exports. */
function filterQuery(): string {
  const parts: string[] = []
  if (selectedRigId.value != null) parts.push(`rig_id=${selectedRigId.value}`)
  if (selectedWellId.value != null) parts.push(`well_id=${selectedWellId.value}`)
  if (fromDateIso.value) parts.push(`from_date=${fromDateIso.value}`)
  if (toDateIso.value) parts.push(`to_date=${toDateIso.value}`)
  if (!includeDraft.value) parts.push('include_draft=false')
  return parts.join('&')
}

function withFilters(extra: string = ''): string {
  const parts = [extra, filterQuery()].filter(Boolean)
  return parts.length ? `?${parts.join('&')}` : ''
}

async function loadLookups(): Promise<void> {
  try {
    const [rigList, wellList, dimensionList] = await Promise.all([
      api.get<RigDropdown[]>('/rig-well/rigs/dropdown'),
      api.get<WellRecord[]>('/rig-well/wells'),
      api.get<ReportDimensionOption[]>('/cost-reports/dimensions'),
    ])
    rigs.value = rigList
    wells.value = wellList
    dimensions.value = dimensionList
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'The report lookups could not be loaded'
  }
}

async function loadReport(): Promise<void> {
  loading.value = true
  actionError.value = null
  drill.value = null
  drillKey.value = null
  try {
    report.value = await api.get<CostReport>(
      `/cost-reports${withFilters(`dimension=${dimension.value}`)}`,
    )
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'The report could not be built'
    report.value = null
  }
  finally {
    loading.value = false
  }
}

async function loadDepthSeries(): Promise<void> {
  if (selectedWellId.value == null) {
    depthSeries.value = null
    return
  }
  try {
    depthSeries.value = await api.get<DepthCostResponse>(
      `/cost-analytics/well/${selectedWellId.value}/depth-cost${includeDraft.value ? '' : '?include_draft=false'}`,
    )
  }
  catch {
    // The chart is a bonus, not the report — a missing well is simply not plotted.
    depthSeries.value = null
  }
}

async function openRow(key: string, label: string): Promise<void> {
  drillKey.value = key
  drillLabel.value = label
  drillLoading.value = true
  try {
    drill.value = await api.get<ReportLineBundle>(
      `/cost-reports/lines${withFilters(`dimension=${dimension.value}&key=${encodeURIComponent(key)}`)}`,
    )
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'The cost lines could not be loaded'
    drill.value = null
  }
  finally {
    drillLoading.value = false
  }
}

function exportReport(format: 'xlsx' | 'csv', detail: boolean): void {
  const detailFlag = detail ? '&detail=true' : ''
  api
    .download(`/cost-reports/export?format=${format}&dimension=${dimension.value}${detailFlag}${filterQuery() ? `&${filterQuery()}` : ''}`)
    .then((blob) => {
      const scope = selectedWell.value?.well_code ?? (selectedRigId.value != null ? 'rig' : 'all')
      triggerDownload(blob, `cost_report_${dimension.value}_${scope}${detail ? '_detail' : ''}.${format}`)
    })
    .catch((error: unknown) => {
      actionError.value = error instanceof Error ? error.message : 'Export failed'
    })
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  window.URL.revokeObjectURL(url)
}

function printPage(): void {
  window.print()
}

function onFromChange(value: Date | Date[] | (Date | null)[] | null | undefined): void {
  fromDate.value = toDate(value)
}

function onToChange(value: Date | Date[] | (Date | null)[] | null | undefined): void {
  toDateValue.value = toDate(value)
}

function rowLabel(row: { key: string, label: string }): string {
  return dimension.value === 'consumable_category'
    ? CONSUMABLE_LABELS[row.key as ConsumableCategory] ?? row.label
    : row.label
}

/** The drill-throughs whose rows carry an AFE estimate to compare with. */
const showsEstimate = computed(
  () => dimension.value === 'section' || dimension.value === 'well',
)

/** Consumable category codes read as their labels in the drill-through. */
function consumableLabel(category: string): string {
  return CONSUMABLE_LABELS[category as ConsumableCategory] ?? category
}

function lineScope(line: ReportLine): string {
  return [line.section, line.phase, line.sub_activity].filter(Boolean).join(' / ') || '—'
}

onMounted(async () => {
  await loadLookups()
  await loadReport()
})

watch(
  [dimension, selectedRigId, selectedWellId, fromDateIso, toDateIso, includeDraft],
  async () => {
    await loadReport()
    if (selectedWellId.value != null) await loadDepthSeries()
  },
)
</script>

<template>
  <div class="reports-page">
    <PageHeader
      class="no-print"
      title="Cost Reports"
      description="The daily costs incurred, drilled through by date, hole section, phase, well activity and sub activity, service, charge category, consumable category, tangible or the overall well. Click any row to see the cost lines behind it, compare them with the AFE estimate, then export or print the report."
    />

    <section class="filters no-print">
      <label class="filter">
        <span class="filter__label">Drill-through</span>
        <Select
          v-model="dimension"
          :options="dimensionOptions"
          option-label="label"
          option-value="value"
          size="small"
          class="filter__select"
        />
      </label>
      <label class="filter">
        <span class="filter__label">Rig</span>
        <Select
          v-model="selectedRigId"
          :options="rigs"
          option-label="display_name"
          option-value="id"
          placeholder="All rigs"
          show-clear
          filter
          size="small"
          class="filter__select"
        />
      </label>
      <label class="filter">
        <span class="filter__label">Well</span>
        <Select
          v-model="selectedWellId"
          :options="wellOptions"
          option-label="label"
          option-value="value"
          placeholder="All wells"
          show-clear
          filter
          size="small"
          class="filter__select"
        />
      </label>
      <label class="filter filter__date">
        <span class="filter__label">From</span>
        <DatePicker
          :model-value="fromDate"
          date-format="dd-mm-yy"
          size="small"
          show-icon
          @update:model-value="onFromChange"
        />
      </label>
      <label class="filter filter__date">
        <span class="filter__label">To</span>
        <DatePicker
          :model-value="toDateValue"
          date-format="dd-mm-yy"
          size="small"
          show-icon
          @update:model-value="onToChange"
        />
      </label>
      <label class="filter filter__check">
        <Checkbox v-model="includeDraft" :binary="true" input-id="report-include-draft" />
        <span>Include draft days</span>
      </label>
      <div class="filter__actions">
        <Button label="Detail XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportReport('xlsx', true)" />
        <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportReport('xlsx', false)" />
        <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportReport('csv', false)" />
        <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printPage" />
      </div>
    </section>

    <Message v-if="actionError" severity="error" :closable="false" class="no-print" @close="actionError = null">
      {{ actionError }}
    </Message>

    <section v-if="depthSeries && depthSeries.points.length" class="card">
      <header class="card__head">
        <h2 class="card__title">Depth vs Cost — {{ depthSeries.well_code }}</h2>
        <span class="card__subtitle">
          AFE estimated cost against the actual cost at each hole section depth
        </span>
      </header>
      <DepthCostChart
        :points="depthSeries.points"
        :depth-unit="depthSeries.depth_unit"
        :total-estimated="depthSeries.total_estimated"
        :total-actual="depthSeries.total_actual"
      />
    </section>

    <section class="card">
      <header class="card__head">
        <h2 class="card__title">
          {{ report?.title ?? 'Report' }}
          <span v-if="report" class="card__badge">{{ report.rows.length }} row(s)</span>
        </h2>
        <span class="card__subtitle">
          {{ selectedWell ? `${selectedWell.well_code} - ${selectedWell.well_name}` : (selectedRigId != null ? 'Selected rig' : 'All wells') }}
          · {{ fromDateIso ? formatDateLabel(fromDateIso) : 'no start date' }} →
          {{ toDateIso ? formatDateLabel(toDateIso) : 'today' }}
          · {{ includeDraft ? 'draft days included' : 'submitted days only' }}
          · click a row to drill through
        </span>
      </header>

      <div class="table-scroll">
        <table class="grid" data-testid="cost-report-table">
          <thead>
            <tr>
              <th>{{ dimension === 'consumable_category' ? 'Consumable Category' : report?.title ?? 'Report' }}</th>
              <th class="num">Services</th>
              <th class="num">Consumables</th>
              <th class="num">Tangibles</th>
              <th class="num">Total Cost</th>
              <th v-if="showsEstimate" class="num">AFE Estimated</th>
              <th v-if="showsEstimate" class="num">Balance</th>
              <th class="num">Share</th>
              <th class="no-print" />
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td :colspan="showsEstimate ? 9 : 7" class="empty">
                <i class="pi pi-spin pi-spinner" /> Building the report…
              </td>
            </tr>
            <tr v-else-if="!report || report.rows.length === 0">
              <td :colspan="showsEstimate ? 9 : 7" class="empty">
                No cost lines match these filters — save and submit daily costs to report them.
              </td>
            </tr>
            <tr
              v-for="row in report?.rows ?? []"
              :key="row.key"
              class="grid__row"
              :class="{ 'grid__row--active': row.key === drillKey }"
              @click="openRow(row.key, row.label)"
            >
              <td class="truncate" :title="row.label">{{ rowLabel(row) }}</td>
              <td class="num mono">{{ formatMoney(row.services) }}</td>
              <td class="num mono">{{ formatMoney(row.consumables) }}</td>
              <td class="num mono">{{ formatMoney(row.tangibles) }}</td>
              <td class="num mono"><strong>{{ formatMoney(row.total) }}</strong></td>
              <td v-if="showsEstimate" class="num mono">{{ formatMoney(row.estimated) }}</td>
              <td v-if="showsEstimate" class="num mono" :class="{ 'is-over': Number(row.balance) < 0 }">
                {{ formatMoney(row.balance) }}
              </td>
              <td class="num">
                {{ report && Number(report.totals.total)
                  ? `${formatQuantity((Number(row.total) / Number(report.totals.total)) * 100)}%`
                  : '—' }}
              </td>
              <td class="num no-print">
                <Button
                  icon="pi pi-angle-right"
                  size="small"
                  severity="secondary"
                  text
                  aria-label="Drill through"
                  @click.stop="openRow(row.key, row.label)"
                />
              </td>
            </tr>
          </tbody>
          <tfoot v-if="report && report.rows.length">
            <tr>
              <td>Total</td>
              <td class="num mono">{{ formatMoney(report.totals.services) }}</td>
              <td class="num mono">{{ formatMoney(report.totals.consumables) }}</td>
              <td class="num mono">{{ formatMoney(report.totals.tangibles) }}</td>
              <td class="num mono"><strong>{{ formatMoney(report.totals.total) }}</strong></td>
              <td v-if="showsEstimate" class="num mono">{{ formatMoney(report.totals.estimated) }}</td>
              <td v-if="showsEstimate" class="num mono" :class="{ 'is-over': Number(report.totals.balance) < 0 }">
                {{ formatMoney(report.totals.balance) }}
              </td>
              <td class="num">100%</td>
              <td class="no-print" />
            </tr>
          </tfoot>
        </table>
      </div>
      <p v-if="report && !showsEstimate && Number(report.totals.estimated)" class="card__foot">
        AFE estimated cost for the selected wells:
        <strong class="mono">{{ formatMoney(report.totals.estimated) }}</strong> · balance remaining
        <strong class="mono" :class="{ 'is-over': Number(report.totals.balance) < 0 }">
          {{ formatMoney(report.totals.balance) }}
        </strong>
        (the estimate is only split by hole section, so this drill-through reports the actual cost).
      </p>
    </section>

    <section v-if="drillKey" class="card" data-testid="cost-report-drill">
      <header class="card__head">
        <h2 class="card__title">
          Cost lines — {{ drillLabel }}
          <span v-if="drill" class="card__badge">{{ drill.line_count }} line(s)</span>
        </h2>
        <span class="card__subtitle">
          Total
          <strong class="mono">{{ drill ? formatMoney(String(drill.total)) : '—' }}</strong>
          · every line behind this report row
        </span>
      </header>
      <div class="table-scroll">
        <table class="grid grid--tight">
          <thead>
            <tr>
              <th>Cost Date</th>
              <th>Daily Cost</th>
              <th>Group</th>
              <th>Category</th>
              <th>Code</th>
              <th>Description</th>
              <th>Section / Phase / Sub Activity</th>
              <th class="num">Qty</th>
              <th>Unit</th>
              <th class="num">Rate</th>
              <th class="num">Amount</th>
              <th>Status</th>
              <th>Remarks</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="drillLoading">
              <td colspan="13" class="empty"><i class="pi pi-spin pi-spinner" /> Loading the cost lines…</td>
            </tr>
            <tr v-else-if="!drill || drill.lines.length === 0">
              <td colspan="13" class="empty">No cost lines for this row.</td>
            </tr>
            <tr v-for="(line, index) in drill?.lines ?? []" :key="`${line.cost_date}-${index}`">
              <td>{{ formatDateLabel(line.cost_date) }}</td>
              <td class="mono">{{ line.daily_cost_code }}</td>
              <td>{{ line.cost_group }}</td>
              <td>{{ dimension === 'consumable_category' ? consumableLabel(line.category) : line.category }}</td>
              <td class="mono">{{ line.code }}</td>
              <td class="truncate" :title="line.name">{{ line.name }}</td>
              <td class="truncate" :title="lineScope(line)">{{ lineScope(line) }}</td>
              <td class="num">{{ formatQuantity(line.quantity) }}</td>
              <td>{{ line.unit }}</td>
              <td class="num mono">{{ formatMoney(line.rate) }}</td>
              <td class="num mono"><strong>{{ formatMoney(line.amount) }}</strong></td>
              <td>{{ line.status === 'submitted' ? 'Submitted' : 'Draft' }}</td>
              <td class="truncate" :title="line.remarks">{{ line.remarks }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
  .reports-page {
    display: grid;
    gap: 12px;
  }

  .filters {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    flex-wrap: wrap;
    background: var(--app-surface);
    border: 1px solid var(--app-border);
    border-radius: 12px;
    box-shadow: var(--app-shadow);
    padding: 10px 12px;
  }

  .filter {
    display: grid;
    gap: 3px;
    min-width: 170px;
  }

  .filter__date {
    min-width: 150px;
  }

  .filter__label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--app-text-muted, #6b7480);
    font-weight: 600;
  }

  .filter__select {
    width: 100%;
  }

  .filter__check {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.78rem;
    padding-bottom: 5px;
    min-width: 0;
  }

  .filter__actions {
    display: flex;
    gap: 6px;
    margin-left: auto;
    padding-bottom: 2px;
    flex-wrap: wrap;
  }

  .card {
    background: var(--app-surface);
    border: 1px solid var(--app-border);
    border-radius: 12px;
    box-shadow: var(--app-shadow);
    padding: 12px 14px;
    display: grid;
    gap: 10px;
  }

  .card__head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .card__title {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 650;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .card__badge {
    font-size: 0.66rem;
    font-weight: 600;
    padding: 1px 8px;
    border-radius: 999px;
    background: var(--app-surface-muted, #eef2f7);
    color: var(--app-text-muted, #4b5563);
  }

  .card__subtitle {
    font-size: 0.72rem;
    color: var(--app-text-muted, #6b7480);
  }

  .card__foot {
    margin: 0;
    font-size: 0.72rem;
    color: var(--app-text-muted, #5b6472);
  }

  .table-scroll {
    overflow-x: auto;
  }

  .grid {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.76rem;
  }

  .grid th,
  .grid td {
    border-bottom: 1px solid var(--app-border-soft, #eef1f6);
    padding: 5px 8px;
    text-align: left;
    white-space: nowrap;
  }

  .grid th {
    background: var(--app-surface-muted, #f7f9fc);
    color: var(--app-text-muted, #5b6472);
    font-weight: 600;
  }

  .grid--tight th,
  .grid--tight td {
    padding: 3px 8px;
    font-size: 0.72rem;
  }

  .grid tfoot td {
    background: var(--app-surface-muted, #f4f7fb);
    font-weight: 650;
    border-top: 1px solid var(--app-border, #dfe5ee);
  }

  .grid__row {
    cursor: pointer;
  }

  .grid__row:hover td {
    background: var(--app-surface-muted, #f5f8fc);
  }

  .grid__row--active td {
    background: #eef4ff;
  }

  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .mono {
    font-family: var(--app-font-mono, ui-monospace, monospace);
  }

  .truncate {
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .is-over {
    color: #b91c1c;
    font-weight: 650;
  }

  .empty {
    text-align: center;
    color: var(--app-text-muted, #7c8593);
    padding: 14px !important;
  }
</style>
