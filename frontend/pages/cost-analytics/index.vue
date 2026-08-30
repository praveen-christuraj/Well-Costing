<script setup lang="ts">
/**
 * Cost Analytics — the AFE estimated cost against the actual cost incurred.
 *
 * The table lists every well with its AFE budget, the actual cost from the
 * saved daily costs, the balance remaining and the forecast at well completion
 * (the burn rate of the days worked, projected across the planned days left).
 * Opening a well shows the comparison per cost group, the Depth vs Cost curve
 * — depth from the well configuration, estimated cost from the AFE cost
 * estimates, actual cost at that depth from the daily costs — and the same
 * rollups the Reports page offers.
 *
 * Reconciliation is shown, not hidden: until a reconciliation run has marked
 * the days reconciled, the actual cost is reported as unreconciled.
 */
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Message from 'primevue/message'
import Select from 'primevue/select'
import PageHeader from '~/components/design-system/PageHeader.vue'
import DepthCostChart from '~/components/daily-cost/DepthCostChart.vue'
import { formatDateLabel, formatMoney, formatQuantity } from '~/utils/dailyCost'
import {
  CONSUMABLE_LABELS,
  type ConsumableCategory,
  type WellAnalytics,
  type WellAnalyticsSummary,
} from '~/types/dailyCost'
import { matchesAdvancedSearch } from '~/utils/search'

definePageMeta({ middleware: 'auth' })

const api = useApi()

interface RigDropdown { id: number, rig_code: string, rig_name: string, display_name: string }

const rigs = ref<RigDropdown[]>([])
const selectedRigId = ref<number | null>(null)
const search = ref('')
const includeDraft = ref(true)
const rows = ref<WellAnalyticsSummary[]>([])
const loading = ref(false)
const actionError = ref<string | null>(null)

const selectedWellId = ref<number | null>(null)
const detail = ref<WellAnalytics | null>(null)
const detailLoading = ref(false)

/** Rollups shown under the selected well, in the order the user asked for. */
const DIMENSION_ORDER: { key: string, title: string }[] = [
  { key: 'section', title: 'Cost by Hole Section' },
  { key: 'phase', title: 'Cost by Phase' },
  { key: 'activity', title: 'Cost by Well Activity' },
  { key: 'sub_activity', title: 'Cost by Well Sub Activity' },
  { key: 'service', title: 'Cost by Service' },
  { key: 'charge_category', title: 'Cost by Charge Category' },
  { key: 'consumable_category', title: 'Cost by Consumable Category' },
  { key: 'tangible', title: 'Cost by Tangible' },
  { key: 'date', title: 'Cost by Date' },
]

const filteredRows = computed(() =>
  rows.value.filter(row => matchesAdvancedSearch(row, search.value)),
)

function query(extra: string = ''): string {
  const parts: string[] = []
  if (selectedRigId.value != null) parts.push(`rig_id=${selectedRigId.value}`)
  if (!includeDraft.value) parts.push('include_draft=false')
  if (extra) parts.push(extra)
  return parts.length ? `?${parts.join('&')}` : ''
}

async function loadRigs(): Promise<void> {
  try {
    rigs.value = await api.get<RigDropdown[]>('/rig-well/rigs/dropdown')
    if (selectedRigId.value != null && !rigs.value.some(rig => rig.id === selectedRigId.value)) {
      selectedRigId.value = null
    }
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'Rigs could not be loaded'
  }
}

async function loadRows(): Promise<void> {
  loading.value = true
  actionError.value = null
  try {
    rows.value = await api.get<WellAnalyticsSummary[]>(`/cost-analytics/wells${query()}`)
    if (selectedWellId.value != null && !rows.value.some(row => row.well_id === selectedWellId.value)) {
      selectedWellId.value = null
      detail.value = null
    }
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'Cost analytics could not be loaded'
  }
  finally {
    loading.value = false
  }
}

async function loadDetail(wellId: number | null): Promise<void> {
  selectedWellId.value = wellId
  if (wellId == null) {
    detail.value = null
    return
  }
  detailLoading.value = true
  try {
    detail.value = await api.get<WellAnalytics>(
      `/cost-analytics/well/${wellId}${includeDraft.value ? '' : '?include_draft=false'}`,
    )
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'The well analytics could not be loaded'
    detail.value = null
  }
  finally {
    detailLoading.value = false
  }
}

function exportRows(format: 'xlsx' | 'csv'): void {
  api
    .download(`/cost-analytics/wells/export?format=${format}${query().replace('?', '&')}`)
    .then((blob) => {
      triggerDownload(blob, `cost_analytics.${format}`)
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

function utilisationOf(row: WellAnalyticsSummary): string {
  return row.utilisation == null ? '—' : `${formatQuantity(row.utilisation)}%`
}

function consumableLabel(category: string): string {
  return CONSUMABLE_LABELS[category as ConsumableCategory] ?? category
}

onMounted(() => {
  void loadRigs()
  void loadRows()
})

watch([selectedRigId, includeDraft], async () => {
  await loadRows()
  if (selectedWellId.value != null) await loadDetail(selectedWellId.value)
})
</script>

<template>
  <div class="analytics-page">
    <PageHeader
      class="no-print"
      title="Cost Analytics"
      description="AFE estimated cost versus the actual cost incurred from the saved daily costs, with the balance remaining and a forecast at well completion. Depth versus cost compares the AFE cost estimates with the actual cost at each hole section depth."
    />

    <section class="filters no-print">
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
      <label class="filter filter__search">
        <span class="filter__label">Search</span>
        <input v-model="search" type="search" class="filter__input" placeholder="Well code, name or status…">
      </label>
      <label class="filter filter__check">
        <Checkbox v-model="includeDraft" :binary="true" input-id="include-draft" />
        <span>Include draft days</span>
      </label>
      <div class="filter__actions">
        <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportRows('xlsx')" />
        <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportRows('csv')" />
        <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printPage" />
      </div>
    </section>

    <Message v-if="actionError" severity="error" :closable="false" class="no-print" @close="actionError = null">
      {{ actionError }}
    </Message>

    <section class="card">
      <header class="card__head">
        <h2 class="card__title">Well cost position</h2>
        <span class="card__subtitle">
          {{ filteredRows.length }} well(s) · click a well for its analytics
        </span>
      </header>
      <div class="table-scroll">
        <table class="grid">
          <thead>
            <tr>
              <th>Well</th>
              <th>Rig</th>
              <th>Status</th>
              <th class="num">AFEs</th>
              <th class="num">AFE Estimated</th>
              <th class="num">Actual Cost</th>
              <th class="num">Balance</th>
              <th class="num">Utilisation</th>
              <th class="num">Planned / Elapsed days</th>
              <th class="num">Forecast at Completion</th>
              <th class="num">Variance</th>
              <th class="no-print" />
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="12" class="empty"><i class="pi pi-spin pi-spinner" /> Loading cost analytics…</td>
            </tr>
            <tr v-else-if="filteredRows.length === 0">
              <td colspan="12" class="empty">No wells match — daily costs appear here once a day is saved.</td>
            </tr>
            <tr
              v-for="row in filteredRows"
              :key="row.well_id"
              class="grid__row"
              :class="{ 'grid__row--active': row.well_id === selectedWellId }"
              @click="loadDetail(row.well_id)"
            >
              <td class="truncate" :title="`${row.well_code} - ${row.well_name}`">
                <strong>{{ row.well_code }}</strong> — {{ row.well_name }}
              </td>
              <td class="truncate">{{ row.rig_code || '—' }}</td>
              <td>{{ row.well_status || '—' }}</td>
              <td class="num">{{ row.afe_count }}</td>
              <td class="num mono">{{ formatMoney(row.estimated_total) }}</td>
              <td class="num mono">{{ formatMoney(row.actual_total) }}</td>
              <td class="num mono" :class="{ 'is-over': Number(row.balance) < 0 }">
                {{ formatMoney(row.balance) }}
              </td>
              <td class="num">{{ utilisationOf(row) }}</td>
              <td class="num">
                {{ formatQuantity(row.planned_days) }} / {{ formatQuantity(row.elapsed_days) }}
              </td>
              <td class="num mono">{{ formatMoney(row.forecast_at_completion) }}</td>
              <td class="num mono" :class="{ 'is-over': Number(row.forecast_variance) > 0 }">
                {{ formatMoney(row.forecast_variance) }}
              </td>
              <td class="num no-print">
                <Button
                  icon="pi pi-chart-line"
                  size="small"
                  severity="secondary"
                  text
                  aria-label="Open analytics"
                  @click.stop="loadDetail(row.well_id)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <template v-if="detail">
      <section class="card">
        <header class="card__head">
          <h2 class="card__title">
            {{ detail.well.well_code }} — {{ detail.well.well_name }}
            <span class="card__badge">{{ detail.well.well_status || 'No status' }}</span>
          </h2>
          <span class="card__subtitle">
            {{ detail.afes.length }} AFE(s) ·
            {{ detail.well.days_with_cost }} day(s) with cost ·
            {{ formatDateLabel(detail.well.first_cost_date) }} →
            {{ formatDateLabel(detail.well.last_cost_date) }}
          </span>
        </header>

        <div class="compare">
          <div v-for="row in detail.comparisons" :key="row.group" class="compare__card">
            <span class="compare__label">{{ row.group }}</span>
            <span class="compare__row"><span>AFE estimated</span><strong class="mono">{{ formatMoney(row.estimated) }}</strong></span>
            <span class="compare__row"><span>Actual incurred</span><strong class="mono">{{ formatMoney(row.actual) }}</strong></span>
            <span class="compare__row compare__row--balance">
              <span>Balance remaining</span>
              <strong class="mono" :class="{ 'is-over': Number(row.balance) < 0 }">{{ formatMoney(row.balance) }}</strong>
            </span>
          </div>
          <div class="compare__card compare__card--total">
            <span class="compare__label">Whole well</span>
            <span class="compare__row"><span>AFE estimated</span><strong class="mono">{{ formatMoney(detail.well.estimated_total) }}</strong></span>
            <span class="compare__row"><span>Actual incurred</span><strong class="mono">{{ formatMoney(detail.well.actual_total) }}</strong></span>
            <span class="compare__row compare__row--balance">
              <span>Balance remaining</span>
              <strong class="mono" :class="{ 'is-over': Number(detail.well.balance) < 0 }">
                {{ formatMoney(detail.well.balance) }}
              </strong>
            </span>
          </div>
        </div>

        <div class="forecast" data-testid="cost-forecast">
          <h3 class="forecast__title">Forecast at well completion</h3>
          <dl class="forecast__grid">
            <div><dt>Actual to date</dt><dd class="mono">{{ formatMoney(detail.forecast.actual_to_date) }}</dd></div>
            <div><dt>Burn rate / day</dt><dd class="mono">{{ formatMoney(detail.forecast.burn_rate_per_day) }}</dd></div>
            <div><dt>Planned days</dt><dd>{{ formatQuantity(detail.forecast.planned_days) }}</dd></div>
            <div><dt>Days worked</dt><dd>{{ formatQuantity(detail.forecast.elapsed_days) }}</dd></div>
            <div><dt>Days remaining</dt><dd>{{ formatQuantity(detail.forecast.remaining_days) }}</dd></div>
            <div><dt>Forecast at completion</dt><dd class="mono">{{ formatMoney(detail.forecast.forecast_at_completion) }}</dd></div>
            <div><dt>Variance to AFE</dt><dd class="mono" :class="{ 'is-over': Number(detail.forecast.variance) > 0 }">{{ formatMoney(detail.forecast.variance) }}</dd></div>
            <div><dt>Balance at completion</dt><dd class="mono" :class="{ 'is-over': Number(detail.forecast.balance_at_completion) < 0 }">{{ formatMoney(detail.forecast.balance_at_completion) }}</dd></div>
          </dl>
          <p class="forecast__basis">{{ detail.forecast.basis }}</p>
        </div>

        <Message
          v-if="Number(detail.well.unreconciled_total) > 0"
          severity="warn"
          :closable="false"
          class="no-print"
        >
          {{ formatMoney(detail.well.unreconciled_total) }} of the actual cost is not reconciled yet
          ({{ formatMoney(detail.well.reconciled_total) }} reconciled). Reconciliation runs between
          the daily entries and this comparison.
        </Message>

        <ul v-if="detail.warnings.length" class="notes">
          <li v-for="warning in detail.warnings" :key="warning">
            <i class="pi pi-info-circle" /> {{ warning }}
          </li>
        </ul>
      </section>

      <section class="card">
        <header class="card__head">
          <h2 class="card__title">Depth vs Cost</h2>
          <span class="card__subtitle">
            Depth from the well configuration · estimated from the AFE cost estimates · actual at
            that depth from the daily costs
          </span>
        </header>
        <DepthCostChart
          :points="detail.depth_series"
          :depth-unit="detail.well.depth_unit"
          :total-estimated="detail.well.estimated_total"
          :total-actual="detail.well.actual_total"
        />
        <ul v-if="detail.depth_notes.length" class="notes">
          <li v-for="note in detail.depth_notes" :key="note"><i class="pi pi-info-circle" /> {{ note }}</li>
        </ul>
        <p v-if="Number(detail.unattributed_actual) > 0" class="notes__line">
          Actual cost with no section scope (well-wide services and tangibles):
          <strong class="mono">{{ formatMoney(detail.unattributed_actual) }}</strong>
        </p>
      </section>

      <section class="card">
        <header class="card__head">
          <h2 class="card__title">Cost rollups</h2>
          <span class="card__subtitle">The same drill-throughs the Reports page offers</span>
        </header>
        <div class="rollups">
          <div v-for="dimension in DIMENSION_ORDER" :key="dimension.key" class="rollup">
            <h3 class="rollup__title">{{ dimension.title }}</h3>
            <table class="grid grid--tight">
              <thead>
                <tr>
                  <th>{{ dimension.key === 'consumable_category' ? 'Category' : 'Name' }}</th>
                  <th class="num">Services</th>
                  <th class="num">Consumables</th>
                  <th class="num">Tangibles</th>
                  <th class="num">Total</th>
                  <th class="num">AFE Estimated</th>
                  <th class="num">Balance</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!(detail.dimensions[dimension.key] ?? []).length">
                  <td colspan="7" class="empty">No cost recorded for this dimension yet.</td>
                </tr>
                <tr v-for="row in detail.dimensions[dimension.key] ?? []" :key="row.key">
                  <td class="truncate" :title="row.label">
                    {{ dimension.key === 'consumable_category' ? consumableLabel(row.label) : row.label }}
                  </td>
                  <td class="num mono">{{ formatMoney(row.services) }}</td>
                  <td class="num mono">{{ formatMoney(row.consumables) }}</td>
                  <td class="num mono">{{ formatMoney(row.tangibles) }}</td>
                  <td class="num mono"><strong>{{ formatMoney(row.total) }}</strong></td>
                  <td class="num mono">{{ Number(row.estimated) ? formatMoney(row.estimated) : '—' }}</td>
                  <td class="num mono" :class="{ 'is-over': Number(row.balance) < 0 }">
                    {{ Number(row.estimated) ? formatMoney(row.balance) : '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="card">
        <header class="card__head">
          <h2 class="card__title">Daily cost trend</h2>
          <span class="card__subtitle">Actual cost per day and cumulative</span>
        </header>
        <table class="grid grid--tight">
          <thead>
            <tr>
              <th>Cost Date</th>
              <th class="num">Cost of the Day</th>
              <th class="num">Cumulative</th>
              <th class="num">Share of AFE</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="detail.daily_trend.length === 0">
              <td colspan="4" class="empty">No daily costs recorded for this well yet.</td>
            </tr>
            <tr v-for="point in detail.daily_trend" :key="point.cost_date">
              <td>{{ formatDateLabel(point.cost_date) }}</td>
              <td class="num mono">{{ formatMoney(point.amount) }}</td>
              <td class="num mono">{{ formatMoney(point.cumulative) }}</td>
              <td class="num">
                {{ Number(detail.well.estimated_total)
                  ? `${formatQuantity((Number(point.cumulative) / Number(detail.well.estimated_total)) * 100)}%`
                  : '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .analytics-page {
    display: grid;
    gap: 12px;
  }

  .filters {
    display: flex;
    align-items: flex-end;
    gap: 14px;
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
    min-width: 180px;
  }

  .filter__search {
    min-width: 240px;
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

  .filter__input {
    border: 1px solid var(--app-border, #d8dee7);
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 0.78rem;
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
    position: sticky;
    top: 0;
  }

  .grid--tight th,
  .grid--tight td {
    padding: 3px 8px;
    font-size: 0.73rem;
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
    max-width: 260px;
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

  .compare {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 10px;
  }

  .compare__card {
    border: 1px solid var(--app-border, #e3e7ee);
    border-radius: 10px;
    padding: 8px 10px;
    display: grid;
    gap: 2px;
    background: var(--app-surface-muted, #fafcfe);
  }

  .compare__card--total {
    background: #eef4ff;
    border-color: #c7d8fb;
  }

  .compare__label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--app-text-muted, #6b7480);
    font-weight: 600;
  }

  .compare__row {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    font-size: 0.76rem;
  }

  .compare__row--balance {
    border-top: 1px solid var(--app-border, #e3e7ee);
    margin-top: 3px;
    padding-top: 3px;
  }

  .forecast {
    border: 1px solid var(--app-border, #e3e7ee);
    border-radius: 10px;
    padding: 10px 12px;
    background: var(--app-surface-muted, #fafcfe);
  }

  .forecast__title {
    margin: 0 0 6px;
    font-size: 0.82rem;
    font-weight: 650;
  }

  .forecast__grid {
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 6px 14px;
  }

  .forecast__grid dt {
    font-size: 0.66rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--app-text-muted, #6b7480);
  }

  .forecast__grid dd {
    margin: 0;
    font-size: 0.82rem;
    font-weight: 650;
  }

  .forecast__basis {
    margin: 8px 0 0;
    font-size: 0.72rem;
    color: var(--app-text-muted, #5b6472);
  }

  .notes {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 3px;
  }

  .notes li {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.72rem;
    color: #b45309;
  }

  .notes__line {
    margin: 0;
    font-size: 0.72rem;
    color: var(--app-text-muted, #5b6472);
  }

  .rollups {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(430px, 1fr));
    gap: 12px;
  }

  .rollup__title {
    margin: 0 0 4px;
    font-size: 0.78rem;
    font-weight: 650;
  }
</style>
