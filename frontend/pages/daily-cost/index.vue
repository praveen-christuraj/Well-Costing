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
const currentDepth = ref<number | null>(null)
const dailyProgress = ref<number | null>(null)
const operationalSummary = ref<string>('')

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
const selectedWell = computed(() => wells.value.find(w => w.id === selectedWellId.value))

/* -------------------------------- Calculations ---------------------------- */
function computeServiceAmount(line: DailyCostServiceLine): number {
  const hours = Number(line.service_hours) || 0
  const rate = Number(line.unit_rate) || 0
  const days = hours / 24.0
  line.operating_days = Number(days.toFixed(4))

  if (line.rate_basis === 'daily') {
    const amt = days * rate
    line.amount = Number(amt.toFixed(2))
    return line.amount
  }
  line.amount = Number(rate.toFixed(2))
  return line.amount
}

function computeConsumableAmount(line: DailyCostConsumableLine): number {
  const qty = Number(line.quantity) || 0
  const rate = Number(line.unit_rate) || 0
  const amt = qty * rate
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
    service_hours: 24.0,
    operating_days: 1.0,
    rate_basis: (defaultSvc?.rate_basis as any) || 'daily',
    unit_rate: defaultSvc?.operating_rate ?? 0,
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
          service_hours: 24.0,
          operating_days: 1.0,
          rate_basis: (item.rate_basis as any) || 'daily',
          unit_rate: matchRef?.operating_rate ?? 0,
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
      current_depth: currentDepth.value !== null ? Number(currentDepth.value) : null,
      daily_progress: dailyProgress.value !== null ? Number(dailyProgress.value) : null,
      operational_summary: operationalSummary.value || null,
      services: serviceLines.value.map(s => ({
        service_id: s.service_id,
        cost_code_id: s.cost_code_id,
        vendor_id: s.vendor_id || null,
        hole_section_id: s.hole_section_id || entryHoleSectionId.value || null,
        service_hours: Number(s.service_hours) || 0,
        rate_basis: s.rate_basis,
        unit_rate: Number(s.unit_rate) || 0,
        remarks: s.remarks || null,
      })),
      consumables: consumableLines.value.map(c => ({
        consumable_id: c.consumable_id,
        cost_code_id: c.cost_code_id,
        vendor_id: c.vendor_id || null,
        quantity: Number(c.quantity) || 0,
        unit_id: c.unit_id,
        unit_rate: Number(c.unit_rate) || 0,
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

async function loadDayData(): Promise<void> {
  if (!selectedWellId.value) return
  loading.value = true
  try {
    const entry = await api.getEntry(selectedWellId.value, formattedDate.value)
    if (entry) {
      entryHoleSectionId.value = entry.hole_section_id ?? null
      entryPhase.value = entry.phase ?? (phases.value[0]?.name ?? 'Drilling')
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
    ])
    refServices.value = refRates.services || []
    refConsumables.value = refRates.consumables || []

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
    const [wellsPage, phaseList, sectionPage, codePage, unitPage] = await Promise.all([
      afeApi.listWells(),
      afeApi.listDrillingPhases(),
      master.list('hole-sections'),
      master.list('cost-codes'),
      master.list('units'),
    ])
    wells.value = wellsPage.items || []
    phases.value = phaseList || []
    holeSections.value = sectionPage.items.filter(s => s.is_active)
    costCodes.value = codePage.items
    units.value = unitPage.items

    if (wells.value.length) {
      selectedWellId.value = wells.value[0].id
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
        <Button label="Save Day Log" icon="pi pi-save" :loading="saving" :disabled="!selectedWellId" @click="saveDailyCost" />
      </template>
    </PageHeader>

    <Message v-if="success" severity="success" :closable="true" @close="success = null">{{ success }}</Message>
    <Message v-if="error" severity="error" :closable="true" @close="error = null">{{ error }}</Message>

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
          <label>Phase</label>
          <Select v-model="entryPhase" :options="phases" option-label="name" option-value="name" fluid />
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
              <Column header="#" style="width: 50px">
                <template #body="{ index }">{{ index + 1 }}</template>
              </Column>
              <Column header="Service Item" style="min-width: 240px">
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
              <Column header="Section" style="width: 140px">
                <template #body="{ data }">
                  <Select v-model="data.hole_section_id" :options="holeSections" option-label="code" option-value="id" placeholder="Section" show-clear fluid size="small" />
                </template>
              </Column>
              <Column header="Hours (0-24)" style="width: 130px">
                <template #body="{ data }">
                  <InputNumber
                    v-model="data.service_hours"
                    :min="0"
                    :max="24"
                    :max-fraction-digits="2"
                    fluid
                    size="small"
                    @input="computeServiceAmount(data)"
                  />
                </template>
              </Column>
              <Column header="Operating Days" style="width: 120px">
                <template #body="{ data }">
                  <Tag :value="`${(Number(data.service_hours || 0) / 24).toFixed(4)} d`" severity="secondary" />
                </template>
              </Column>
              <Column header="Rate Basis" style="width: 140px">
                <template #body="{ data }">
                  <Select
                    v-model="data.rate_basis"
                    :options="[
                      { label: 'Daily rate', value: 'daily' },
                      { label: 'Per section', value: 'per_section' },
                      { label: 'Per service', value: 'per_service' },
                      { label: 'Fixed', value: 'fixed' },
                    ]"
                    option-label="label"
                    option-value="value"
                    fluid
                    size="small"
                    @change="computeServiceAmount(data)"
                  />
                </template>
              </Column>
              <Column header="Rate ($)" style="width: 130px">
                <template #body="{ data }">
                  <InputNumber
                    v-model="data.unit_rate"
                    :min="0"
                    :max-fraction-digits="2"
                    fluid
                    size="small"
                    @input="computeServiceAmount(data)"
                  />
                </template>
              </Column>
              <Column header="Daily Amount ($)" style="width: 140px">
                <template #body="{ data }">
                  <strong>${{ Number(data.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</strong>
                </template>
              </Column>
              <Column header="Remarks" style="min-width: 150px">
                <template #body="{ data }">
                  <InputText v-model="data.remarks" fluid size="small" placeholder="Notes/activity" />
                </template>
              </Column>
              <Column header="" style="width: 50px">
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
              <Column header="#" style="width: 50px">
                <template #body="{ index }">{{ index + 1 }}</template>
              </Column>
              <Column header="Chemical / Additive" style="min-width: 240px">
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
              <Column header="Usage Quantity" style="width: 140px">
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
              <Column header="Unit" style="width: 110px">
                <template #body="{ data }">
                  <Select v-model="data.unit_id" :options="units" option-label="code" option-value="id" fluid size="small" />
                </template>
              </Column>
              <Column header="Unit Rate ($)" style="width: 130px">
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
              <Column header="Total Cost ($)" style="width: 140px">
                <template #body="{ data }">
                  <strong>${{ Number(data.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</strong>
                </template>
              </Column>
              <Column header="Remarks" style="min-width: 150px">
                <template #body="{ data }">
                  <InputText v-model="data.remarks" fluid size="small" placeholder="Purpose / mud treatment" />
                </template>
              </Column>
              <Column header="" style="width: 50px">
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
  </div>
</template>

<style scoped>
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
