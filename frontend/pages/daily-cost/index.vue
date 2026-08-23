<script setup lang="ts">
/**
 * Daily Cost Entry & Operational AFE Analysis.
 *
 * Daily operational data entry:
 * 1. Services utilized: service hours / 24 = operating days, multiplied by
 *    daily rate or charged per section, per service, or fixed.
 * 2. Chemicals and additives consumed: quantity multiplied by unit rate.
 *
 * Live comparative analytics:
 * - Compares daily & cumulative spend against the AFE budget
 * - Calculates remaining balance and daily burn rate
 * - Forecasts end-of-well cost based on remaining planned days
 * - Visualizes 5-day / 7-day trends and drill-through service consumption.
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import DatePicker from 'primevue/datepicker'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import PageHeader from '~/components/design-system/PageHeader.vue'
import { escapeHtml, formatMoneyCell, printDocument } from '~/utils/printDocument'
import type { AfeRecord, DrillingPhaseRecord, WellRecord } from '~/types/afe'
import type {
  DailyCostAnalytics,
  DailyCostConsumableLine,
  DailyCostServiceLine,
  ReferenceConsumableRate,
  ReferenceServiceRate,
} from '~/types/dailyCost'
import type { MasterDataRecord } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const api = useDailyCost()
const afeApi = useAfe()
const master = useMasterData()
const wellActApi = useWellActivities()

const wells = ref<WellRecord[]>([])
const selectedWellId = ref<string>('')
const selectedDate = ref<Date>(new Date())

const activeAfe = ref<AfeRecord | null>(null)
const phases = ref<DrillingPhaseRecord[]>([])
const holeSections = ref<MasterDataRecord[]>([])
const costCodes = ref<MasterDataRecord[]>([])
const units = ref<MasterDataRecord[]>([])

const refServices = ref<ReferenceServiceRate[]>([])
const refConsumables = ref<ReferenceConsumableRate[]>([])

const activeTab = ref<string>('services')
const trendRange = ref<'5' | '7' | 'all'>('7')

// Daily Header Info
const entryHoleSectionId = ref<string | null>(null)
const entryPhase = ref<string>('Drilling')
const entrySubActivityId = ref<string | null>(null)
const currentDepth = ref<number | null>(null)
const dailyProgress = ref<number | null>(null)
const operationalSummary = ref<string>('')

// The AFE Cost Estimate that supplies the unit rates (single source of rates).
const ratesAfeCode = ref<string | null>(null)
const ratesUnpricedCount = ref<number>(0)

// Lines
const serviceLines = ref<DailyCostServiceLine[]>([])
const consumableLines = ref<DailyCostConsumableLine[]>([])

// Analytics
const analytics = ref<DailyCostAnalytics | null>(null)

// UI State
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

// Chart DOM refs
const trendChartEl = ref<HTMLElement | null>(null)
const breakdownChartEl = ref<HTMLElement | null>(null)
let trendChartInstance: echarts.ECharts | null = null
let breakdownChartInstance: echarts.ECharts | null = null

function toDateString(value: Date | null): string {
  if (!value) return new Date().toISOString().slice(0, 10)
  const offset = value.getTimezoneOffset() * 60000
  return new Date(value.getTime() - offset).toISOString().slice(0, 10)
}

const formattedDate = computed(() => toDateString(selectedDate.value))
const wellActivities = computed(() => wellActApi.wellActivities.value)

/* --------------------------- Sub-activity configuration -------------------
 * Activities (Planned, NPT, UPA) are master data and never edited here.
 * Sub-activities are well-scoped and configured exactly where they are needed:
 * while the day's costs are being entered, without leaving the page.
 */
const activities = ref<MasterDataRecord[]>([])
const subActivityDialog = ref(false)
const savingSubActivity = ref(false)
const subActivityForm = ref({ activity_id: '', name: '', responsible_party: '', description: '' })

function openSubActivityDialog(): void {
  subActivityForm.value = {
    activity_id: activities.value[0]?.id ?? '',
    name: '',
    responsible_party: '',
    description: '',
  }
  subActivityDialog.value = true
}

async function saveSubActivity(): Promise<void> {
  if (!selectedWellId.value || !subActivityForm.value.activity_id || !subActivityForm.value.name.trim()) return
  savingSubActivity.value = true
  error.value = null
  try {
    const created = await wellActApi.createActivity({
      well_id: selectedWellId.value,
      activity_id: subActivityForm.value.activity_id,
      name: subActivityForm.value.name.trim(),
      responsible_party: subActivityForm.value.responsible_party.trim() || null,
      description: subActivityForm.value.description.trim() || null,
    })
    if (!created) {
      error.value = wellActApi.error.value ?? 'The sub-activity could not be saved.'
      return
    }
    success.value = `Sub-activity ${created.name} is ready to use.`
    subActivityDialog.value = false
  }
  finally { savingSubActivity.value = false }
}

/* -------------------------------- Calculations ---------------------------- */
function computeServiceAmount(line: DailyCostServiceLine): number {
  const hours = Number(line.service_hours) || 0
  const baseRate = Number(line.unit_rate) || 0
  // Override rate takes precedence if present
  const effectiveRate = (line.override_rate != null && Number(line.override_rate) > 0)
    ? Number(line.override_rate)
    : baseRate
  const days = hours / 24.0
  line.operating_days = Number(days.toFixed(4))

  if (line.rate_basis === 'daily') {
    // Daily rate: hours / 24 * daily rate
    const amt = days * effectiveRate
    line.amount = Number(amt.toFixed(2))
    return line.amount
  }
  if (line.rate_basis === 'per_section') {
    // Per section: flat rate per section selected
    line.amount = Number(effectiveRate.toFixed(2))
    return line.amount
  }
  if (line.rate_basis === 'per_service') {
    // Per service: flat rate from AFE for this service
    line.amount = Number(effectiveRate.toFixed(2))
    return line.amount
  }
  if (line.rate_basis === 'fixed') {
    // Fixed rate: one-time charge from AFE, override available
    line.amount = Number(effectiveRate.toFixed(2))
    return line.amount
  }
  line.amount = Number(effectiveRate.toFixed(2))
  return line.amount
}

function computeConsumableAmount(line: DailyCostConsumableLine): number {
  const qty = Number(line.quantity) || 0
  const baseRate = Number(line.unit_rate) || 0
  // Override rate takes precedence if present
  const effectiveRate = (line.override_rate != null && Number(line.override_rate) > 0)
    ? Number(line.override_rate)
    : baseRate
  const amt = qty * effectiveRate
  line.amount = Number(amt.toFixed(2))
  return line.amount
}

const totalDailyServices = computed(() => serviceLines.value.reduce((sum, line) => sum + (Number(line.amount) || 0), 0))
const totalDailyConsumables = computed(() => consumableLines.value.reduce((sum, line) => sum + (Number(line.amount) || 0), 0))
const totalDailyCost = computed(() => totalDailyServices.value + totalDailyConsumables.value)

/* ------------------------------ Line Management --------------------------- */
function addServiceLine(): void {
  const defaultSvc = refServices.value[0]
  serviceLines.value.push({
    service_id: defaultSvc?.service_id ?? '',
    service_code: defaultSvc?.service_code ?? '',
    service_name: defaultSvc?.service_name ?? '',
    cost_code_id: defaultSvc?.cost_code_id ?? (costCodes.value[0]?.id ?? ''),
    cost_code: defaultSvc?.cost_code ?? '',
    vendor_id: defaultSvc?.vendor_id ?? null,
    vendor_name: defaultSvc?.vendor_name ?? null,
    hole_section_id: entryHoleSectionId.value,
    sub_activity_id: null,
    service_type: 'operation',
    service_hours: 24.0,
    operating_days: 1.0,
    rate_basis: (defaultSvc?.rate_basis as DailyCostServiceLine['rate_basis']) || 'daily',
    unit_rate: defaultSvc?.operating_rate ?? 0,
    override_rate: null,
    amount: defaultSvc?.operating_rate ?? 0,
    remarks: '',
  })
}

function onServiceSelect(line: DailyCostServiceLine): void {
  const match = refServices.value.find(s => s.service_id === line.service_id)
  if (match) {
    line.service_code = match.service_code
    line.service_name = match.service_name
    line.cost_code_id = match.cost_code_id
    line.cost_code = match.cost_code
    line.vendor_id = match.vendor_id ?? null
    line.vendor_name = match.vendor_name ?? null
    line.rate_basis = match.rate_basis
    line.unit_rate = match.operating_rate
    // For per_section, prompt for section selection; for fixed/per_service, rate auto-populates
    if (match.rate_basis === 'per_section') {
      line.hole_section_id = entryHoleSectionId.value
    }
    computeServiceAmount(line)
  }
}

function removeServiceLine(index: number): void {
  serviceLines.value.splice(index, 1)
}

function addConsumableLine(): void {
  const defaultCon = refConsumables.value[0]
  consumableLines.value.push({
    consumable_id: defaultCon?.consumable_id ?? '',
    consumable_code: defaultCon?.consumable_code ?? '',
    consumable_name: defaultCon?.consumable_name ?? '',
    cost_code_id: defaultCon?.cost_code_id ?? (costCodes.value[0]?.id ?? ''),
    cost_code: defaultCon?.cost_code ?? '',
    quantity: 10,
    unit_id: defaultCon?.unit_id ?? (units.value[0]?.id ?? ''),
    unit_code: defaultCon?.unit_code ?? 'EA',
    unit_rate: defaultCon?.unit_rate ?? 0,
    amount: (10 * (defaultCon?.unit_rate ?? 0)),
    remarks: '',
  })
}

function onConsumableSelect(line: DailyCostConsumableLine): void {
  const match = refConsumables.value.find(c => c.consumable_id === line.consumable_id)
  if (match) {
    line.consumable_code = match.consumable_code
    line.consumable_name = match.consumable_name
    line.cost_code_id = match.cost_code_id
    line.cost_code = match.cost_code
    line.unit_id = match.unit_id
    line.unit_code = match.unit_code
    line.unit_rate = match.unit_rate
    computeConsumableAmount(line)
  }
}

function removeConsumableLine(index: number): void {
  consumableLines.value.splice(index, 1)
}

function quickLoadAfeItems(): void {
  if (!activeAfe.value || !activeAfe.value.items?.length) {
    error.value = 'No AFE lines found on the active AFE to load.'
    return
  }
  for (const item of activeAfe.value.items) {
    if (item.item_type === 'service') {
      const matchRef = refServices.value.find(s => s.service_id === item.catalog_item_id)
      const existing = serviceLines.value.find(s => s.service_id === item.catalog_item_id)
      if (!existing) {
        serviceLines.value.push({
          service_id: item.catalog_item_id,
          service_code: item.catalog_item_code,
          service_name: item.catalog_item_name,
          cost_code_id: item.cost_code_id,
          cost_code: item.cost_code,
          hole_section_id: item.hole_section_id || entryHoleSectionId.value,
          sub_activity_id: null,
          service_type: 'operation',
          service_hours: 24.0,
          operating_days: 1.0,
          rate_basis: (item.rate_basis as DailyCostServiceLine['rate_basis']) || 'daily',
          unit_rate: matchRef?.operating_rate ?? 0,
          override_rate: null,
          amount: matchRef?.operating_rate ?? 0,
          remarks: item.notes ?? '',
        })
      }
    }
    else {
      const matchCon = refConsumables.value.find(c => c.consumable_id === item.catalog_item_id)
      const existing = consumableLines.value.find(c => c.consumable_id === item.catalog_item_id)
      if (!existing) {
        const qty = Number(item.daily_consumption) || Number(item.quantity) || 1
        const rate = matchCon?.unit_rate ?? 0
        consumableLines.value.push({
          consumable_id: item.catalog_item_id,
          consumable_code: item.catalog_item_code,
          consumable_name: item.catalog_item_name,
          cost_code_id: item.cost_code_id,
          cost_code: item.cost_code,
          quantity: qty,
          unit_id: item.unit_id,
          unit_code: item.unit_code,
          unit_rate: rate,
          amount: qty * rate,
          remarks: item.notes ?? '',
        })
      }
    }
  }
  success.value = 'Loaded services and consumables from AFE scope.'
}

/* ------------------------------- Save & Load ------------------------------ */
async function saveDailyCost(): Promise<void> {
  if (!selectedWellId.value) return
  if (!entrySubActivityId.value) {
    error.value = wellActivities.value.length
      ? 'Select the day\u2019s activity type (Planned, NPT-1, UPA-1, …) before saving.'
      : 'No activity types are configured for this well yet. Configure the Well Activities page first so Planned, NPT, and UPA costs are accounted properly.'
    return
  }
  saving.value = true
  error.value = null
  success.value = null
  try {
    serviceLines.value.forEach(computeServiceAmount)
    consumableLines.value.forEach(computeConsumableAmount)

    const payload = {
      well_id: selectedWellId.value,
      afe_id: activeAfe.value?.id ?? null,
      entry_date: formattedDate.value,
      hole_section_id: entryHoleSectionId.value || null,
      phase: entryPhase.value || null,
      sub_activity_id: entrySubActivityId.value,
      current_depth: currentDepth.value !== null ? Number(currentDepth.value) : null,
      daily_progress: dailyProgress.value !== null ? Number(dailyProgress.value) : null,
      operational_summary: operationalSummary.value || null,
      services: serviceLines.value.map(s => ({
        service_id: s.service_id,
        cost_code_id: s.cost_code_id,
        vendor_id: s.vendor_id || null,
        hole_section_id: s.hole_section_id || entryHoleSectionId.value || null,
        sub_activity_id: s.sub_activity_id || entrySubActivityId.value || null,
        service_type: s.service_type || 'operation',
        service_hours: Number(s.service_hours) || 0,
        rate_basis: s.rate_basis,
        unit_rate: Number(s.unit_rate) || 0,
        override_rate: s.override_rate != null && Number(s.override_rate) > 0 ? Number(s.override_rate) : null,
        remarks: s.remarks || null,
      })),
      consumables: consumableLines.value.map(c => ({
        consumable_id: c.consumable_id,
        cost_code_id: c.cost_code_id,
        vendor_id: c.vendor_id || null,
        sub_activity_id: c.sub_activity_id || entrySubActivityId.value || null,
        quantity: Number(c.quantity) || 0,
        unit_id: c.unit_id,
        unit_rate: Number(c.unit_rate) || 0,
        override_rate: c.override_rate != null && Number(c.override_rate) > 0 ? Number(c.override_rate) : null,
        remarks: c.remarks || null,
      })),
    }

    await api.saveEntry(selectedWellId.value, payload)
    success.value = `Daily cost data for ${formattedDate.value} saved successfully.`
    await loadDayData()
    await loadAnalytics()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Could not save daily cost entry.'
  }
  finally { saving.value = false }
}

/* ------------------------------ Daily reports ----------------------------- */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

async function exportDayReport(): Promise<void> {
  if (!selectedWellId.value) return
  try {
    downloadBlob(
      await api.exportDayReport(selectedWellId.value, formattedDate.value),
      `daily-cost-report-${formattedDate.value}.xlsx`,
    )
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The day report export failed. Save the day log first.'
  }
}

async function exportRegister(): Promise<void> {
  if (!selectedWellId.value) return
  try {
    downloadBlob(await api.exportRegister(selectedWellId.value), 'daily-cost-register.xlsx')
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The register export failed.'
  }
}

/** Print a record-quality daily cost report for the selected day. */
function printDayReport(): void {
  const well = wells.value.find(candidate => candidate.id === selectedWellId.value)
  const activityName = wellActivities.value.find(item => item.id === entrySubActivityId.value)?.name ?? '—'
  const meta = [
    ['Well', `${well?.code ?? ''} — ${well?.name ?? ''}`],
    ['Rig', well?.rig_name ?? '—'],
    ['AFE', activeAfe.value ? `${activeAfe.value.code} — ${activeAfe.value.title}` : '—'],
    ['Report date', formattedDate.value],
    ['Phase', entryPhase.value || '—'],
    ['Hole section', holeSections.value.find(section => section.id === entryHoleSectionId.value)?.code ?? '—'],
    ['Activity type', activityName],
    ['Current depth', currentDepth.value != null ? String(currentDepth.value) : '—'],
    ['24h progress', dailyProgress.value != null ? String(dailyProgress.value) : '—'],
  ]
  const metaHtml = meta
    .map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join('')
  const serviceRows = serviceLines.value.map(line => `
    <tr>
      <td>${escapeHtml(line.service_code)}<br><small>${escapeHtml(line.service_name)}</small></td>
      <td>${escapeHtml(line.service_type || 'operation')}</td>
      <td class="num">${Number(line.service_hours) || 0}</td>
      <td class="num">${Number(line.operating_days) || 0}</td>
      <td>${escapeHtml(line.rate_basis)}</td>
      <td class="num">${formatMoneyCell(line.unit_rate)}</td>
      <td class="num">${line.override_rate != null && Number(line.override_rate) > 0 ? formatMoneyCell(line.override_rate) : '—'}</td>
      <td class="num">${formatMoneyCell(line.amount)}</td>
      <td>${escapeHtml(line.remarks ?? '')}</td>
    </tr>`).join('')
  const consumableRows = consumableLines.value.map(line => `
    <tr>
      <td>${escapeHtml(line.consumable_code)}<br><small>${escapeHtml(line.consumable_name)}</small></td>
      <td class="num">${Number(line.quantity) || 0}</td>
      <td>${escapeHtml(line.unit_code ?? '')}</td>
      <td class="num">${formatMoneyCell(line.unit_rate)}</td>
      <td class="num">${line.override_rate != null && Number(line.override_rate) > 0 ? formatMoneyCell(line.override_rate) : '—'}</td>
      <td class="num">${formatMoneyCell(line.amount)}</td>
      <td>${escapeHtml(line.remarks ?? '')}</td>
    </tr>`).join('')
  printDocument(`Daily Cost Report ${formattedDate.value}`, `
    <h1>DAILY COST REPORT</h1>
    <p class="doc-subtitle">Unit rates are read from the AFE Cost Estimates${ratesAfeCode.value ? ` of AFE ${escapeHtml(ratesAfeCode.value)}` : ''}; overrides are shown where applied.</p>
    <div class="meta-grid">${metaHtml}</div>
    <h2>Services utilised</h2>
    <table>
      <thead><tr><th>Service</th><th>Type</th><th class="num">Hours</th><th class="num">Days</th><th>Rate basis</th><th class="num">Unit rate</th><th class="num">Override</th><th class="num">Amount</th><th>Remarks</th></tr></thead>
      <tbody>${serviceRows || '<tr><td colspan="9">No services recorded.</td></tr>'}
        <tr class="total-row"><td colspan="7">Total services</td><td class="num">${formatMoneyCell(totalDailyServices.value)}</td><td></td></tr>
      </tbody>
    </table>
    <h2>Chemicals &amp; consumables</h2>
    <table>
      <thead><tr><th>Consumable</th><th class="num">Qty</th><th>Unit</th><th class="num">Unit rate</th><th class="num">Override</th><th class="num">Amount</th><th>Remarks</th></tr></thead>
      <tbody>${consumableRows || '<tr><td colspan="7">No consumables recorded.</td></tr>'}
        <tr class="total-row"><td colspan="5">Total consumables</td><td class="num">${formatMoneyCell(totalDailyConsumables.value)}</td><td></td></tr>
        <tr class="total-row"><td colspan="5">Total daily cost</td><td class="num">${formatMoneyCell(totalDailyCost.value)}</td><td></td></tr>
      </tbody>
    </table>
    <h2>Operational summary</h2>
    <p>${escapeHtml(operationalSummary.value || '—')}</p>
    <div class="signatures"><div>Prepared by</div><div>Day supervisor</div><div>Company representative</div></div>
    <p class="print-footer">Printed ${new Date().toLocaleString()} — Daily Cost, well scoped.</p>
  `)
}

async function loadDayData(): Promise<void> {
  if (!selectedWellId.value) return
  loading.value = true
  try {
    const entry = await api.getEntry(selectedWellId.value, formattedDate.value)
    if (entry) {
      entryHoleSectionId.value = entry.hole_section_id ?? null
      entryPhase.value = entry.phase ?? (phases.value[0]?.name ?? 'Drilling')
      entrySubActivityId.value = entry.sub_activity_id ?? null
      currentDepth.value = entry.current_depth !== null ? Number(entry.current_depth) : null
      dailyProgress.value = entry.daily_progress !== null ? Number(entry.daily_progress) : null
      operationalSummary.value = entry.operational_summary ?? ''
      serviceLines.value = (entry.services || []).map(s => ({
        ...s,
        service_hours: Number(s.service_hours),
        operating_days: Number(s.operating_days),
        unit_rate: Number(s.unit_rate),
        amount: Number(s.amount),
      }))
      consumableLines.value = (entry.consumables || []).map(c => ({
        ...c,
        quantity: Number(c.quantity),
        unit_rate: Number(c.unit_rate),
        amount: Number(c.amount),
      }))
    }
    else {
      // Clear or prefill from previous / defaults
      entryPhase.value = phases.value[0]?.name ?? 'Drilling'
      entrySubActivityId.value = null
      currentDepth.value = null
      dailyProgress.value = null
      operationalSummary.value = ''
      serviceLines.value = []
      consumableLines.value = []
    }
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Failed to load day data.'
  }
  finally { loading.value = false }
}

async function loadAnalytics(): Promise<void> {
  if (!selectedWellId.value) return
  try {
    analytics.value = await api.getAnalytics(selectedWellId.value)
    await nextTick()
    renderCharts()
  }
  catch (caught: unknown) {
    console.error('Analytics load error:', caught)
  }
}

async function onWellChange(): Promise<void> {
  if (!selectedWellId.value) return
  try {
    const [refRates, afesPage] = await Promise.all([
      api.getReferenceRates(selectedWellId.value),
      afeApi.listAfes(selectedWellId.value),
      wellActApi.loadForWell(selectedWellId.value),
    ])
    refServices.value = refRates.services || []
    refConsumables.value = refRates.consumables || []
    ratesAfeCode.value = refRates.afe_code ?? null
    ratesUnpricedCount.value = refRates.unpriced_line_count ?? 0

    const wellAfes = afesPage.items || []
    activeAfe.value = wellAfes.find(a => a.status === 'submitted') ?? wellAfes[0] ?? null

    await loadDayData()
    await loadAnalytics()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Could not load well references.'
  }
}

/* --------------------------------- Charts --------------------------------- */
function renderCharts(): void {
  if (!analytics.value) return

  // 1. Trend Chart
  if (trendChartEl.value) {
    if (!trendChartInstance) trendChartInstance = echarts.init(trendChartEl.value)

    let points = analytics.value.trend_all_days || []
    if (trendRange.value === '5') points = analytics.value.trend_last_5_days || []
    else if (trendRange.value === '7') points = analytics.value.trend_last_7_days || []

    const dates = points.map(p => p.entry_date)
    const servicesSpend = points.map(p => Number(p.services_cost || 0))
    const consumablesSpend = points.map(p => Number(p.consumables_cost || 0))
    const cumulativeSpend = points.map(p => Number(p.cumulative_cost || 0))

    trendChartInstance.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
      },
      legend: {
        data: ['Services ($)', 'Chemicals ($)', 'Cumulative ($)'],
        top: 0,
      },
      grid: { left: '3%', right: '4%', bottom: '8%', containLabel: true },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { rotate: 25, fontSize: 11 },
      },
      yAxis: [
        {
          type: 'value',
          name: 'Daily Spend ($)',
          axisLabel: { formatter: (v: number) => `$${(v / 1000).toFixed(0)}k` },
        },
        {
          type: 'value',
          name: 'Cumulative ($)',
          axisLabel: { formatter: (v: number) => `$${(v / 1000).toFixed(0)}k` },
        },
      ],
      series: [
        {
          name: 'Services ($)',
          type: 'bar',
          stack: 'Daily',
          itemStyle: { color: '#3b82f6' },
          data: servicesSpend,
        },
        {
          name: 'Chemicals ($)',
          type: 'bar',
          stack: 'Daily',
          itemStyle: { color: '#10b981' },
          data: consumablesSpend,
        },
        {
          name: 'Cumulative ($)',
          type: 'line',
          yAxisIndex: 1,
          itemStyle: { color: '#f59e0b' },
          lineStyle: { width: 3 },
          data: cumulativeSpend,
        },
      ],
    })
  }

  // 2. Service Consumption Breakdown Chart
  if (breakdownChartEl.value) {
    if (!breakdownChartInstance) breakdownChartInstance = echarts.init(breakdownChartEl.value)

    const svcData = (analytics.value.services_breakdown || []).map(s => ({
      name: s.service_name || s.service_code,
      value: Number(s.total_cost || 0),
    }))

    breakdownChartInstance.setOption({
      tooltip: {
        trigger: 'item',
        formatter: '{b}: ${c} ({d}%)',
      },
      legend: {
        orient: 'vertical',
        left: 'left',
        top: 'middle',
        textStyle: { fontSize: 11 },
      },
      series: [
        {
          name: 'Services Spend',
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['65%', '50%'],
          avoidLabelOverlap: true,
          itemStyle: {
            borderRadius: 6,
            borderColor: '#fff',
            borderWidth: 2,
          },
          label: { show: false },
          emphasis: {
            label: {
              show: true,
              fontSize: 12,
              fontWeight: 'bold',
            },
          },
          data: svcData.length ? svcData : [{ name: 'No data', value: 0 }],
        },
      ],
    })
  }
}

async function loadAll(): Promise<void> {
  loading.value = true
  try {
    const [wellsPage, phaseList, sectionPage, codePage, unitPage, activityPage] = await Promise.all([
      afeApi.listWells(),
      // Phases come straight from master data — there is no per-AFE phase list.
      afeApi.listDrillingPhases(),
      master.list('hole-sections'),
      master.list('cost-codes'),
      master.list('units'),
      master.list('activities'),
    ])
    wells.value = wellsPage.items || []
    phases.value = phaseList || []
    activities.value = activityPage.items
    holeSections.value = sectionPage.items.filter(s => s.is_active)
    costCodes.value = codePage.items
    units.value = unitPage.items

    const firstWell = wells.value[0]
    if (firstWell) {
      selectedWellId.value = firstWell.id
      await onWellChange()
    }
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Failed to initialize daily cost module.'
  }
  finally { loading.value = false }
}

watch([selectedDate, trendRange], () => {
  void loadDayData()
  renderCharts()
})

onMounted(() => void loadAll())
</script>

<template>
  <div class="daily-cost-page">
    <PageHeader
      title="Daily Cost Tracker & AFE Analysis"
      description="Track daily operational service hours and chemical usage. Service hours (divided by 24 for operating days) calculate rate amounts according to daily, per-section, per-service, or fixed terms. Quantities multiply by unit prices. Live cumulative spend is compared with AFE budget, balance, burn rate, and end-of-well forecast."
    >
      <template #actions>
        <Button label="Print Day Report" icon="pi pi-print" text :disabled="!selectedWellId" @click="printDayReport" />
        <Button label="Day Report (Excel)" icon="pi pi-file-excel" text :disabled="!selectedWellId" @click="exportDayReport" />
        <Button label="Export Register" icon="pi pi-download" outlined :disabled="!selectedWellId" @click="exportRegister" />
        <Button label="Save Day Log" icon="pi pi-save" :loading="saving" :disabled="!selectedWellId" @click="saveDailyCost" />
      </template>
    </PageHeader>

    <Message v-if="success" severity="success" :closable="true" @close="success = null">{{ success }}</Message>
    <Message v-if="error" severity="error" :closable="true" @close="error = null">{{ error }}</Message>

    <Message v-if="selectedWellId && !wellActivities.length" severity="warn" :closable="false">
      No activity types (Planned, NPT, UPA sub-activities) are configured for this well yet.
      Daily cost entry requires one — configure the
      <NuxtLink to="/daily-cost/well-activities">Well Activities page</NuxtLink> first so every cost is
      accounted to Planned, NPT, or UPA.
    </Message>
    <Message v-else-if="selectedWellId && ratesAfeCode" severity="info" :closable="false">
      Unit rates are read from the <strong>AFE Cost Estimates</strong> of AFE
      <strong>{{ ratesAfeCode }}</strong>.
      <template v-if="ratesUnpricedCount > 0">
        {{ ratesUnpricedCount }} AFE line(s) still have no unit rate — set them on the
        <NuxtLink to="/afe-cost-estimates">AFE Cost Estimates page</NuxtLink>.
      </template>
      A per-line override remains available for exceptional days.
    </Message>

    <!-- Top Controls & Selector Bar -->
    <section class="dc-selector-bar bulk-grid-panel">
      <div class="selector-field">
        <label>Select Well</label>
        <Select
          v-model="selectedWellId"
          :options="wells"
          option-label="code"
          option-value="id"
          placeholder="Select well"
          filter
          style="min-width: 220px"
          @change="onWellChange"
        >
          <template #option="{ option }">
            <strong>{{ option.code }}</strong> — {{ option.name }} ({{ option.rig_name || 'No rig' }})
          </template>
        </Select>
      </div>

      <div class="selector-field">
        <label>Operational Date</label>
        <DatePicker v-model="selectedDate" date-format="yy-mm-dd" show-icon style="width: 170px" @update:model-value="loadDayData" />
      </div>

      <div v-if="activeAfe" class="selector-field afe-badge-field">
        <label>Active AFE</label>
        <div class="afe-tag-box">
          <Tag :value="activeAfe.code" severity="info" />
          <span>{{ activeAfe.title }}</span>
          <Tag :value="activeAfe.status" :severity="activeAfe.status === 'submitted' ? 'success' : 'warn'" />
        </div>
      </div>
    </section>

    <!-- KPI Summary Cards -->
    <section class="dc-kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">Today's Cost ({{ formattedDate }})</span>
        <span class="kpi-value text-primary">${{ totalDailyCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</span>
        <small class="kpi-sub">Services: ${{ totalDailyServices.toFixed(0) }} · Chem: ${{ totalDailyConsumables.toFixed(0) }}</small>
      </div>

      <div class="kpi-card">
        <span class="kpi-label">Cumulative Spend</span>
        <span class="kpi-value text-warn">${{ Number(analytics?.cumulative_actual_cost || totalDailyCost).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</span>
        <small class="kpi-sub">Days logged: {{ analytics?.days_elapsed || 1 }} days</small>
      </div>

      <div class="kpi-card">
        <span class="kpi-label">AFE Budget Amount</span>
        <span class="kpi-value">${{ Number(analytics?.afe_budget || activeAfe?.budget_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</span>
        <small class="kpi-sub">Planned: {{ Number(analytics?.total_planned_days || activeAfe?.total_planned_days || 0).toFixed(1) }} days</small>
      </div>

      <div class="kpi-card" :class="{ 'kpi-card--negative': (analytics?.balance_amount ?? 0) < 0 }">
        <span class="kpi-label">AFE Balance Remaining</span>
        <span class="kpi-value" :class="(analytics?.balance_amount ?? 0) >= 0 ? 'text-success' : 'text-danger'">
          ${{ Number(analytics?.balance_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
        </span>
        <small class="kpi-sub">Daily Burn Rate: ${{ Number(analytics?.burn_rate_daily_avg || 0).toFixed(0) }}/day</small>
      </div>

      <div class="kpi-card">
        <span class="kpi-label">End-of-Well Forecast</span>
        <span class="kpi-value">${{ Number(analytics?.forecast_at_end_of_well || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</span>
        <small class="kpi-sub" :class="(analytics?.variance_to_afe ?? 0) >= 0 ? 'text-success' : 'text-danger'">
          Variance: {{ (analytics?.variance_to_afe ?? 0) >= 0 ? '+' : '' }}${{ Number(analytics?.variance_to_afe || 0).toFixed(0) }}
        </small>
      </div>
    </section>

    <!-- Operational Context Bar -->
    <section class="dc-op-bar bulk-grid-panel">
      <div class="form-row">
        <div class="op-field">
          <label>Activity Type <span class="required-mark">*</span></label>
          <div class="activity-select-row">
            <Select
              v-model="entrySubActivityId"
              :options="wellActivities"
              option-label="name"
              option-value="id"
              :placeholder="wellActivities.length ? 'Planned / NPT / UPA…' : 'Configure Well Activities first'"
              :disabled="!wellActivities.length"
              :invalid="!entrySubActivityId"
              fluid
            >
              <template #option="{ option }">
                <strong>{{ option.name }}</strong>&nbsp;
                <small>({{ option.activity_code || option.activity_name }}<template v-if="option.responsible_party"> · {{ option.responsible_party }}</template>)</small>
              </template>
            </Select>
            <Button icon="pi pi-plus" text size="small" title="Configure a sub-activity" @click="openSubActivityDialog" />
          </div>
        </div>
        <div class="op-field">
          <label>Phase</label>
          <Select
            v-model="entryPhase"
            :options="phases"
            option-label="name"
            option-value="name"
            :placeholder="phases.length ? 'Select phase' : 'Configure phases in master data'"
            :disabled="!phases.length"
            fluid
          />
        </div>
        <div class="op-field">
          <label>Hole Section</label>
          <Select v-model="entryHoleSectionId" :options="holeSections" option-label="code" option-value="id" placeholder="Current section" show-clear fluid />
        </div>
        <div class="op-field">
          <label>Current Depth (m/ft)</label>
          <InputNumber v-model="currentDepth" :min="0" :max-fraction-digits="2" placeholder="e.g. 2450.0" fluid />
        </div>
        <div class="op-field">
          <label>24h Progress</label>
          <InputNumber v-model="dailyProgress" :min="0" :max-fraction-digits="2" placeholder="Footage drilled" fluid />
        </div>
      </div>
    </section>

    <!-- Data Entry Tabs: Services & Chemicals -->
    <Tabs v-model:value="activeTab" class="dc-tabs">
      <TabList>
        <Tab value="services">
          <i class="pi pi-cog" /> Services Used ({{ serviceLines.length }})
        </Tab>
        <Tab value="chemicals">
          <i class="pi pi-box" /> Chemicals & Additives ({{ consumableLines.length }})
        </Tab>
        <Tab value="summary">
          <i class="pi pi-align-left" /> Operations Log
        </Tab>
        <Tab value="analytics">
          <i class="pi pi-chart-line" /> Visual Analytics & AFE Comparison
        </Tab>
      </TabList>

      <TabPanels>
        <!-- TAB 1: SERVICES -->
        <TabPanel value="services">
          <section class="afe-section bulk-grid-panel">
            <div class="grid-toolbar">
              <div>
                <strong>Services Used Today</strong>
                <small class="toolbar-note">Enter service hours. Divided by 24 to compute operating days. Calculated against daily, per-section, per-service, or fixed rates.</small>
              </div>
              <div class="grid-toolbar__actions">
                <Button label="Load from AFE Scope" icon="pi pi-download" text size="small" @click="quickLoadAfeItems" />
                <Button label="Add Service" icon="pi pi-plus" size="small" @click="addServiceLine" />
              </div>
            </div>

            <DataTable :value="serviceLines" data-key="service_id" striped-rows show-gridlines size="small" class="dc-table">
              <Column header="#" style="width: 40px">
                <template #body="{ index }">{{ index + 1 }}</template>
              </Column>
              <Column header="Service Item" style="min-width: 220px">
                <template #body="{ data }">
                  <Select
                    v-model="data.service_id"
                    :options="refServices"
                    option-label="service_name"
                    option-value="service_id"
                    filter
                    fluid
                    size="small"
                    @change="onServiceSelect(data)"
                  >
                    <template #option="{ option }">
                      {{ option.service_code }} — {{ option.service_name }}
                    </template>
                  </Select>
                </template>
              </Column>
              <Column header="Service Type" style="width: 160px">
                <template #body="{ data }">
                  <Select
                    v-model="data.service_type"
                    :options="[
                      { label: 'Equipment Operation', value: 'operation' },
                      { label: 'Equipment Standby', value: 'standby' },
                      { label: 'Mobilization', value: 'mobilisation' },
                      { label: 'Demobilization', value: 'demobilisation' },
                      { label: 'Personnel Operation', value: 'personnel_operation' },
                      { label: 'Personnel Standby', value: 'personnel_standby' },
                      { label: 'Others', value: 'other' },
                    ]"
                    option-label="label"
                    option-value="value"
                    fluid
                    size="small"
                  />
                </template>
              </Column>
              <Column header="Section" style="width: 130px">
                <template #body="{ data }">
                  <Select v-model="data.hole_section_id" :options="holeSections" option-label="code" option-value="id" placeholder="Section" show-clear fluid size="small" />
                </template>
              </Column>
              <Column header="Sub-Activity" style="width: 190px">
                <template #body="{ data }">
                  <div class="sub-activity-cell">
                    <Select
                      v-model="data.sub_activity_id"
                      :options="wellActivities"
                      option-label="name"
                      option-value="id"
                      :placeholder="wellActivities.length ? 'Activity' : 'None configured'"
                      show-clear
                      fluid
                      size="small"
                    />
                    <Button
                      icon="pi pi-plus"
                      text
                      rounded
                      size="small"
                      aria-label="Configure a sub-activity"
                      title="Configure a sub-activity for this well"
                      :disabled="!selectedWellId"
                      @click="openSubActivityDialog"
                    />
                  </div>
                </template>
              </Column>
              <Column header="Hours/Days" style="width: 120px">
                <template #body="{ data }">
                  <InputNumber
                    v-model="data.service_hours"
                    :min="0"
                    :max="24"
                    :max-fraction-digits="2"
                    fluid
                    size="small"
                    :placeholder="data.rate_basis === 'daily' ? 'Hours' : 'Days'"
                    @input="computeServiceAmount(data)"
                  />
                </template>
              </Column>
              <Column header="Days" style="width: 80px">
                <template #body="{ data }">
                  <Tag :value="`${(Number(data.service_hours || 0) / 24).toFixed(2)}d`" severity="secondary" />
                </template>
              </Column>
              <Column header="Rate Basis" style="width: 120px">
                <template #body="{ data }">
                  <Tag :value="data.rate_basis === 'daily' ? 'Daily' : data.rate_basis === 'per_section' ? 'Per Section' : data.rate_basis === 'per_service' ? 'Per Service' : 'Fixed'" :severity="data.rate_basis === 'fixed' ? 'warn' : 'info'" />
                </template>
              </Column>
              <Column header="Unit Rate ($)" style="width: 120px">
                <template #body="{ data }">
                  <InputNumber
                    v-model="data.unit_rate"
                    :min="0"
                    :max-fraction-digits="2"
                    fluid
                    size="small"
                    :disabled="data.rate_basis === 'fixed' || data.rate_basis === 'per_service'"
                    @input="computeServiceAmount(data)"
                  />
                </template>
              </Column>
              <Column header="Override ($)" style="width: 110px">
                <template #body="{ data }">
                  <InputNumber
                    v-model="data.override_rate"
                    :min="0"
                    :max-fraction-digits="2"
                    fluid
                    size="small"
                    placeholder="Override"
                    @input="computeServiceAmount(data)"
                  />
                </template>
              </Column>
              <Column header="Amount ($)" style="width: 120px">
                <template #body="{ data }">
                  <strong>${{ Number(data.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</strong>
                </template>
              </Column>
              <Column header="Remarks" style="min-width: 120px">
                <template #body="{ data }">
                  <InputText v-model="data.remarks" fluid size="small" placeholder="Notes" />
                </template>
              </Column>
              <Column header="" style="width: 40px">
                <template #body="{ index }">
                  <Button icon="pi pi-trash" size="small" text severity="danger" @click="removeServiceLine(index)" />
                </template>
              </Column>
              <template #empty>
                <div class="empty-hint">No services added for today. Click "Add Service" or "Load from AFE Scope".</div>
              </template>
            </DataTable>
          </section>
        </TabPanel>

        <!-- TAB 2: CHEMICALS & ADDITIVES -->
        <TabPanel value="chemicals">
          <section class="afe-section bulk-grid-panel">
            <div class="grid-toolbar">
              <div>
                <strong>Chemicals & Additives Consumed Today</strong>
                <small class="toolbar-note">Select mud chemicals and cement additives. Multiplies usage quantity by unit price.</small>
              </div>
              <div class="grid-toolbar__actions">
                <Button label="Load from AFE Scope" icon="pi pi-download" text size="small" @click="quickLoadAfeItems" />
                <Button label="Add Chemical / Additive" icon="pi pi-plus" size="small" @click="addConsumableLine" />
              </div>
            </div>

            <DataTable :value="consumableLines" data-key="consumable_id" striped-rows show-gridlines size="small" class="dc-table">
              <Column header="#" style="width: 40px">
                <template #body="{ index }">{{ index + 1 }}</template>
              </Column>
              <Column header="Chemical / Additive" style="min-width: 220px">
                <template #body="{ data }">
                  <Select
                    v-model="data.consumable_id"
                    :options="refConsumables"
                    option-label="consumable_name"
                    option-value="consumable_id"
                    filter
                    fluid
                    size="small"
                    @change="onConsumableSelect(data)"
                  >
                    <template #option="{ option }">
                      {{ option.consumable_code }} — {{ option.consumable_name }} ({{ option.unit_code }})
                    </template>
                  </Select>
                </template>
              </Column>
              <Column header="Sub-Activity" style="width: 190px">
                <template #body="{ data }">
                  <div class="sub-activity-cell">
                    <Select
                      v-model="data.sub_activity_id"
                      :options="wellActivities"
                      option-label="name"
                      option-value="id"
                      :placeholder="wellActivities.length ? 'Activity' : 'None configured'"
                      show-clear
                      fluid
                      size="small"
                    />
                    <Button
                      icon="pi pi-plus"
                      text
                      rounded
                      size="small"
                      aria-label="Configure a sub-activity"
                      title="Configure a sub-activity for this well"
                      :disabled="!selectedWellId"
                      @click="openSubActivityDialog"
                    />
                  </div>
                </template>
              </Column>
              <Column header="Quantity" style="width: 120px">
                <template #body="{ data }">
                  <InputNumber
                    v-model="data.quantity"
                    :min="0"
                    :max-fraction-digits="2"
                    fluid
                    size="small"
                    @input="computeConsumableAmount(data)"
                  />
                </template>
              </Column>
              <Column header="Unit" style="width: 100px">
                <template #body="{ data }">
                  <Select v-model="data.unit_id" :options="units" option-label="code" option-value="id" fluid size="small" />
                </template>
              </Column>
              <Column header="Unit Rate ($)" style="width: 120px">
                <template #body="{ data }">
                  <InputNumber
                    v-model="data.unit_rate"
                    :min="0"
                    :max-fraction-digits="2"
                    fluid
                    size="small"
                    @input="computeConsumableAmount(data)"
                  />
                </template>
              </Column>
              <Column header="Override ($)" style="width: 110px">
                <template #body="{ data }">
                  <InputNumber
                    v-model="data.override_rate"
                    :min="0"
                    :max-fraction-digits="2"
                    fluid
                    size="small"
                    placeholder="Override"
                    @input="computeConsumableAmount(data)"
                  />
                </template>
              </Column>
              <Column header="Total ($)" style="width: 120px">
                <template #body="{ data }">
                  <strong>${{ Number(data.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</strong>
                </template>
              </Column>
              <Column header="Remarks" style="min-width: 120px">
                <template #body="{ data }">
                  <InputText v-model="data.remarks" fluid size="small" placeholder="Purpose" />
                </template>
              </Column>
              <Column header="" style="width: 40px">
                <template #body="{ index }">
                  <Button icon="pi pi-trash" size="small" text severity="danger" @click="removeConsumableLine(index)" />
                </template>
              </Column>
              <template #empty>
                <div class="empty-hint">No chemicals or additives recorded for today. Click "Add Chemical" or "Load from AFE Scope".</div>
              </template>
            </DataTable>
          </section>
        </TabPanel>

        <!-- TAB 3: OPERATIONS LOG -->
        <TabPanel value="summary">
          <section class="afe-section bulk-grid-panel">
            <strong>24-Hour Operational Summary & Highlights</strong>
            <Textarea
              v-model="operationalSummary"
              rows="8"
              fluid
              placeholder="Enter daily drilling operations log, BHA runs, casing operations, mud density, and remarks for this date..."
              style="margin-top: 0.5rem"
            />
          </section>
        </TabPanel>

        <!-- TAB 4: VISUAL ANALYTICS & CHARTS -->
        <TabPanel value="analytics">
          <section class="afe-section bulk-grid-panel">
            <div class="grid-toolbar">
              <div>
                <strong>Operational Cost Trends & AFE Drill-Through Analytics</strong>
              </div>
              <div class="grid-toolbar__actions">
                <Select
                  v-model="trendRange"
                  :options="[
                    { label: 'Last 5 Days', value: '5' },
                    { label: 'Last 7 Days', value: '7' },
                    { label: 'All Days Drill-Through', value: 'all' },
                  ]"
                  option-label="label"
                  option-value="value"
                  size="small"
                  style="width: 180px"
                  @change="renderCharts"
                />
              </div>
            </div>

            <div class="charts-grid">
              <div class="chart-container">
                <div class="chart-title">Daily Spend & Cumulative Burn vs Plan</div>
                <div ref="trendChartEl" class="chart-canvas" />
              </div>

              <div class="chart-container">
                <div class="chart-title">Consumption Breakdown by Service</div>
                <div ref="breakdownChartEl" class="chart-canvas" />
              </div>
            </div>

            <!-- Breakdown Detail Tables -->
            <div class="analytics-tables-row">
              <div class="analytics-table-col">
                <strong>Service Consumption Summary</strong>
                <DataTable :value="analytics?.services_breakdown || []" size="small" striped-rows show-gridlines class="mt-2">
                  <Column field="service_name" header="Service" />
                  <Column header="Hours">
                    <template #body="{ data }">{{ Number(data.total_hours).toFixed(1) }}h</template>
                  </Column>
                  <Column header="Days">
                    <template #body="{ data }">{{ Number(data.total_days).toFixed(2) }}d</template>
                  </Column>
                  <Column header="Total Spend">
                    <template #body="{ data }"><strong>${{ Number(data.total_cost).toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</strong></template>
                  </Column>
                  <Column header="Share">
                    <template #body="{ data }">{{ Number(data.percentage).toFixed(1) }}%</template>
                  </Column>
                </DataTable>
              </div>

              <div class="analytics-table-col">
                <strong>Chemical & Additive Consumption Summary</strong>
                <DataTable :value="analytics?.consumables_breakdown || []" size="small" striped-rows show-gridlines class="mt-2">
                  <Column field="consumable_name" header="Chemical / Additive" />
                  <Column header="Quantity">
                    <template #body="{ data }">{{ Number(data.total_quantity).toFixed(1) }} {{ data.unit_code }}</template>
                  </Column>
                  <Column header="Total Spend">
                    <template #body="{ data }"><strong>${{ Number(data.total_cost).toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</strong></template>
                  </Column>
                  <Column header="Share">
                    <template #body="{ data }">{{ Number(data.percentage).toFixed(1) }}%</template>
                  </Column>
                </DataTable>
              </div>
            </div>
          </section>
        </TabPanel>
      </TabPanels>
    </Tabs>

    <!--
      Sub-activity configuration. Activities themselves are master data; the
      sub-activities beneath them belong to a single well and are set up here,
      at the moment the day's costs are being recorded.
    -->
    <Dialog v-model:visible="subActivityDialog" modal header="Configure a sub-activity" :style="{ width: '520px' }">
      <p class="dc-dialog-note">
        Sub-activities are scoped to this well and roll up to a master activity — Planned, NPT, or
        UPA — so costs posted against them are accounted to the responsible party.
      </p>
      <div class="dc-dialog-form">
        <label>
          Activity
          <Select
            v-model="subActivityForm.activity_id"
            :options="activities"
            option-label="name"
            option-value="id"
            :placeholder="activities.length ? 'Select activity' : 'Configure activities in master data'"
            :disabled="!activities.length"
            fluid
          />
        </label>
        <label>
          Sub-activity name
          <InputText v-model="subActivityForm.name" placeholder="e.g. NPT-1 Waiting on weather" fluid />
        </label>
        <label>
          Responsible party
          <InputText v-model="subActivityForm.responsible_party" placeholder="e.g. Operator, Rig contractor" fluid />
        </label>
        <label>
          Description
          <Textarea v-model="subActivityForm.description" rows="2" auto-resize fluid />
        </label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="subActivityDialog = false" />
        <Button
          label="Add sub-activity"
          icon="pi pi-check"
          :loading="savingSubActivity"
          :disabled="!subActivityForm.activity_id || !subActivityForm.name.trim()"
          @click="saveSubActivity"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.sub-activity-cell {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.dc-dialog-note {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
  color: var(--text-color-secondary, #64748b);
}

.dc-dialog-form {
  display: grid;
  gap: 0.75rem;
}

.dc-dialog-form label {
  display: grid;
  gap: 0.25rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.daily-cost-page {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.dc-selector-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.5rem;
  padding: 1rem 1.25rem;
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
  letter-spacing: 0.03em;
}

.afe-badge-field {
  flex: 1;
}

.afe-tag-box {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.9rem;
}

.dc-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.kpi-card {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 1rem 1.25rem;
  background: white;
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.kpi-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
}

.kpi-value {
  font-size: 1.45rem;
  font-weight: 700;
  color: #0f172a;
}

.kpi-sub {
  font-size: 0.75rem;
  color: #64748b;
}

.kpi-card--negative {
  border-color: #fca5a5;
  background: #fff5f5;
}

.text-primary {
  color: #2563eb;
}

.text-warn {
  color: #d97706;
}

.text-success {
  color: #16a34a;
}

.text-danger {
  color: #dc2626;
}

.dc-op-bar {
  padding: 0.85rem 1.25rem;
}

.op-field {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.op-field label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
}

.required-mark {
  color: #dc2626;
}

.activity-select-row {
  display: flex;
  gap: 0.25rem;
  align-items: center;
}

.activity-select-row > :first-child {
  flex: 1;
}

.dc-tabs {
  margin-top: 0.25rem;
}

.dc-table {
  margin-top: 0.5rem;
}

.empty-hint {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-style: italic;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
  margin-top: 1rem;
}

.chart-container {
  background: white;
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 8px;
  padding: 1rem;
}

.chart-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: #334155;
  margin-bottom: 0.5rem;
}

.chart-canvas {
  width: 100%;
  height: 300px;
}

.analytics-tables-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
  margin-top: 1.5rem;
}

.analytics-table-col {
  background: white;
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 8px;
  padding: 1rem;
}

.mt-2 {
  margin-top: 0.5rem;
}

@media (max-width: 900px) {
  .charts-grid,
  .analytics-tables-row {
    grid-template-columns: 1fr;
  }
}
</style>
