<script setup lang="ts">
/**
 * Cost Analytics — well-scoped planned-versus-actual comparison.
 *
 * Planned figures come from the AFE (budget, planned days, sections, phases)
 * and the AFE Cost Estimates (priced AFE lines). Actuals come from the daily
 * cost entries. Comparisons: section-wise, activity-wise (Planned / NPT /
 * UPA and sub-activities), phase-wise, date-wise, cumulative, week-wise, and
 * month-wise — as charts and tables, exportable for records.
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
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
import type { WellRecord } from '~/types/afe'
import type { ComparisonBucket, DailyCostComparison } from '~/types/dailyCost'

definePageMeta({ middleware: 'auth' })

const api = useDailyCost()
const afeApi = useAfe()

const wells = ref<WellRecord[]>([])
const selectedWellId = ref<string>('')
const comparison = ref<DailyCostComparison | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const activeTab = ref<string>('date')

const dateChartEl = ref<HTMLElement | null>(null)
const weekChartEl = ref<HTMLElement | null>(null)
const monthChartEl = ref<HTMLElement | null>(null)
const sectionChartEl = ref<HTMLElement | null>(null)
const activityChartEl = ref<HTMLElement | null>(null)
const phaseChartEl = ref<HTMLElement | null>(null)
const charts = new Map<HTMLElement, echarts.ECharts>()

function money(value: string | number | null | undefined): string {
  const numeric = Number(value ?? 0)
  return numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const overBudget = computed(() => Number(comparison.value?.variance_to_budget ?? 0) < 0)

async function loadWells(): Promise<void> {
  const page = await afeApi.listWells()
  wells.value = (page.items || []).filter(w => w.is_active)
  if (!selectedWellId.value && wells.value[0]) {
    selectedWellId.value = wells.value[0].id
    await loadComparison()
  }
}

async function loadComparison(): Promise<void> {
  if (!selectedWellId.value) return
  loading.value = true
  error.value = null
  try {
    comparison.value = await api.getComparison(selectedWellId.value)
    await nextTick()
    renderActiveChart()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Could not load the comparison.'
    comparison.value = null
  }
  finally { loading.value = false }
}

async function exportComparison(): Promise<void> {
  if (!selectedWellId.value) return
  try {
    const blob = await api.exportComparison(selectedWellId.value)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'cost-comparison.xlsx'
    anchor.click()
    URL.revokeObjectURL(url)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The export failed.'
  }
}

function chartFor(element: HTMLElement | null): echarts.ECharts | null {
  if (!element) return null
  let instance = charts.get(element)
  if (!instance) {
    instance = echarts.init(element)
    charts.set(element, instance)
  }
  return instance
}

function renderDateChart(): void {
  const data = comparison.value
  const chart = chartFor(dateChartEl.value)
  if (!chart || !data) return
  const points = data.by_date
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['Operational charges', 'Quantity charges', 'Cumulative actual', 'Planned cumulative'], top: 0 },
    grid: { left: '3%', right: '4%', bottom: '8%', containLabel: true },
    xAxis: { type: 'category', data: points.map(p => p.entry_date), axisLabel: { rotate: 25, fontSize: 11 } },
    yAxis: [
      { type: 'value', name: 'Daily ($)' },
      { type: 'value', name: 'Cumulative ($)' },
    ],
    series: [
      { name: 'Operational charges', type: 'bar', stack: 'daily', itemStyle: { color: '#3b82f6' }, data: points.map(p => Number(p.services_cost)) },
      { name: 'Quantity charges', type: 'bar', stack: 'daily', itemStyle: { color: '#10b981' }, data: points.map(p => Number(p.consumables_cost)) },
      { name: 'Cumulative actual', type: 'line', yAxisIndex: 1, lineStyle: { width: 3 }, itemStyle: { color: '#f59e0b' }, data: points.map(p => Number(p.cumulative_cost)) },
      { name: 'Planned cumulative', type: 'line', yAxisIndex: 1, lineStyle: { width: 2, type: 'dashed' }, itemStyle: { color: '#64748b' }, data: points.map(p => (p.planned_cumulative != null ? Number(p.planned_cumulative) : null)) },
    ],
  })
  chart.resize()
}

function renderBucketBarChart(element: HTMLElement | null, buckets: ComparisonBucket[], withPlanned = false): void {
  const chart = chartFor(element)
  if (!chart) return
  const series: object[] = [
    { name: 'Operational charges', type: 'bar', stack: 'actual', itemStyle: { color: '#3b82f6' }, data: buckets.map(b => Number(b.services_cost)) },
    { name: 'Quantity charges', type: 'bar', stack: 'actual', itemStyle: { color: '#10b981' }, data: buckets.map(b => Number(b.consumables_cost)) },
  ]
  const legend = ['Operational charges', 'Quantity charges']
  if (withPlanned) {
    series.push({ name: 'Planned', type: 'bar', itemStyle: { color: '#94a3b8' }, data: buckets.map(b => (b.planned_cost != null ? Number(b.planned_cost) : 0)) })
    legend.push('Planned')
  }
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: legend, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '8%', containLabel: true },
    xAxis: { type: 'category', data: buckets.map(b => b.label), axisLabel: { rotate: 20, fontSize: 11 } },
    yAxis: { type: 'value', name: 'Cost ($)' },
    series,
  }, true)
  chart.resize()
}

function renderActivityChart(): void {
  const data = comparison.value
  const chart = chartFor(activityChartEl.value)
  if (!chart || !data) return
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: ${c} ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 'middle', textStyle: { fontSize: 11 } },
    series: [{
      name: 'Cost by activity',
      type: 'pie',
      radius: ['38%', '68%'],
      center: ['62%', '50%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      data: data.by_activity.length
        ? data.by_activity.map(b => ({ name: b.label, value: Number(b.total_cost) }))
        : [{ name: 'No data', value: 0 }],
    }],
  }, true)
  chart.resize()
}

function renderActiveChart(): void {
  const data = comparison.value
  if (!data) return
  switch (activeTab.value) {
    case 'date': renderDateChart(); break
    case 'week': renderBucketBarChart(weekChartEl.value, data.by_week); break
    case 'month': renderBucketBarChart(monthChartEl.value, data.by_month); break
    case 'section': renderBucketBarChart(sectionChartEl.value, data.by_section, true); break
    case 'activity': renderActivityChart(); break
    case 'phase': renderBucketBarChart(phaseChartEl.value, data.by_phase); break
  }
}

watch(activeTab, () => { void nextTick().then(renderActiveChart) })

onMounted(() => {
  void loadWells().catch((caught: unknown) => {
    error.value = caught instanceof Error ? caught.message : 'Load failed'
  })
})
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Cost Analytics & Comparison"
      description="Well-scoped comparison of planned versus actual cost: section-wise, activity-wise (Planned / NPT / UPA), phase-wise, date-wise, cumulative, week-wise, and month-wise. Planned figures come from the AFE and its Cost Estimates; actuals from the daily cost entries."
    >
      <template #actions>
        <Button label="Export Excel" icon="pi pi-file-excel" outlined :disabled="!comparison" @click="exportComparison" />
        <Button label="Refresh" icon="pi pi-refresh" :loading="loading" :disabled="!selectedWellId" @click="loadComparison" />
      </template>
    </PageHeader>

    <Message v-if="error" severity="error" :closable="true" @close="error = null">{{ error }}</Message>

    <section class="cmp-selector-bar bulk-grid-panel">
      <div class="selector-field">
        <label>Well</label>
        <Select
          v-model="selectedWellId" :options="wells" option-label="code" option-value="id"
          placeholder="Select well" filter style="min-width: 240px" @change="loadComparison"
        >
          <template #option="{ option }">
            <strong>{{ option.code }}</strong>&nbsp;— {{ option.name }}
          </template>
        </Select>
      </div>
      <div v-if="comparison?.afe_code" class="selector-field">
        <label>Governing AFE</label>
        <div class="afe-tags">
          <Tag :value="comparison.afe_code" severity="info" />
          <span>{{ comparison.afe_title }}</span>
        </div>
      </div>
    </section>

    <section v-if="comparison" class="cmp-kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">AFE Budget</span>
        <span class="kpi-value">${{ money(comparison.afe_budget) }}</span>
        <small class="kpi-sub">Planned days: {{ Number(comparison.total_planned_days).toFixed(1) }}</small>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">AFE Cost Estimate</span>
        <span class="kpi-value">${{ money(comparison.estimate_total) }}</span>
        <small class="kpi-sub">Priced AFE lines (well-scoped rates)</small>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Actual Cumulative</span>
        <span class="kpi-value text-primary">${{ money(comparison.cumulative_actual_cost) }}</span>
        <small class="kpi-sub">{{ comparison.days_elapsed }} day(s) logged</small>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Variance to Budget</span>
        <span class="kpi-value" :class="overBudget ? 'text-danger' : 'text-success'">${{ money(comparison.variance_to_budget) }}</span>
        <small class="kpi-sub">{{ overBudget ? 'Over budget' : 'Within budget' }}</small>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Variance to Estimate</span>
        <span class="kpi-value" :class="Number(comparison.variance_to_estimate) < 0 ? 'text-danger' : 'text-success'">${{ money(comparison.variance_to_estimate) }}</span>
        <small class="kpi-sub">Estimate − actual to date</small>
      </div>
    </section>

    <Message v-if="comparison && !comparison.by_date.length" severity="warn" :closable="false">
      No daily cost entries exist for this well yet. Save day logs on the
      <NuxtLink to="/daily-cost">Daily Cost page</NuxtLink> to populate the comparison.
    </Message>

    <Tabs v-if="comparison" v-model:value="activeTab" class="cmp-tabs">
      <TabList>
        <Tab value="date"><i class="pi pi-calendar" /> Date &amp; Cumulative</Tab>
        <Tab value="week"><i class="pi pi-calendar-plus" /> Week-wise</Tab>
        <Tab value="month"><i class="pi pi-calendar-times" /> Month-wise</Tab>
        <Tab value="section"><i class="pi pi-sitemap" /> Section-wise</Tab>
        <Tab value="activity"><i class="pi pi-flag" /> Activity-wise</Tab>
        <Tab value="phase"><i class="pi pi-compass" /> Phase-wise</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="date">
          <div ref="dateChartEl" class="cmp-chart" />
          <DataTable :value="comparison.by_date" paginator :rows="31" striped-rows show-gridlines class="bulk-grid-panel">
            <Column field="entry_date" header="Date" />
            <Column field="day_number" header="Day #" />
            <Column field="phase" header="Phase" />
            <Column field="hole_section_code" header="Section" />
            <Column field="activity_name" header="Activity" />
            <Column header="Operational charges"><template #body="{ data }">${{ money(data.services_cost) }}</template></Column>
            <Column header="Quantity charges"><template #body="{ data }">${{ money(data.consumables_cost) }}</template></Column>
            <Column header="Daily cost"><template #body="{ data }"><strong>${{ money(data.daily_cost) }}</strong></template></Column>
            <Column header="Cumulative"><template #body="{ data }">${{ money(data.cumulative_cost) }}</template></Column>
            <Column header="Planned cumulative"><template #body="{ data }">{{ data.planned_cumulative != null ? `$${money(data.planned_cumulative)}` : '—' }}</template></Column>
            <Column header="Depth"><template #body="{ data }">{{ data.current_depth ?? '—' }}</template></Column>
          </DataTable>
        </TabPanel>
        <TabPanel value="week">
          <div ref="weekChartEl" class="cmp-chart" />
          <DataTable :value="comparison.by_week" striped-rows show-gridlines class="bulk-grid-panel">
            <Column field="label" header="Week" />
            <Column field="entry_count" header="Days logged" />
            <Column header="Operational charges"><template #body="{ data }">${{ money(data.services_cost) }}</template></Column>
            <Column header="Quantity charges"><template #body="{ data }">${{ money(data.consumables_cost) }}</template></Column>
            <Column header="Total"><template #body="{ data }"><strong>${{ money(data.total_cost) }}</strong></template></Column>
          </DataTable>
        </TabPanel>
        <TabPanel value="month">
          <div ref="monthChartEl" class="cmp-chart" />
          <DataTable :value="comparison.by_month" striped-rows show-gridlines class="bulk-grid-panel">
            <Column field="label" header="Month" />
            <Column field="entry_count" header="Days logged" />
            <Column header="Operational charges"><template #body="{ data }">${{ money(data.services_cost) }}</template></Column>
            <Column header="Quantity charges"><template #body="{ data }">${{ money(data.consumables_cost) }}</template></Column>
            <Column header="Total"><template #body="{ data }"><strong>${{ money(data.total_cost) }}</strong></template></Column>
          </DataTable>
        </TabPanel>
        <TabPanel value="section">
          <div ref="sectionChartEl" class="cmp-chart" />
          <DataTable :value="comparison.by_section" striped-rows show-gridlines class="bulk-grid-panel">
            <Column field="label" header="Hole section" />
            <Column header="Planned (estimate)"><template #body="{ data }">{{ data.planned_cost != null ? `$${money(data.planned_cost)}` : '—' }}</template></Column>
            <Column header="Planned days"><template #body="{ data }">{{ data.planned_days != null ? Number(data.planned_days).toFixed(1) : '—' }}</template></Column>
            <Column header="Actual operational"><template #body="{ data }">${{ money(data.services_cost) }}</template></Column>
            <Column header="Actual quantity"><template #body="{ data }">${{ money(data.consumables_cost) }}</template></Column>
            <Column header="Actual total"><template #body="{ data }"><strong>${{ money(data.total_cost) }}</strong></template></Column>
            <Column header="Variance">
              <template #body="{ data }">
                <span v-if="data.variance != null" :class="Number(data.variance) < 0 ? 'text-danger' : 'text-success'">${{ money(data.variance) }}</span>
                <span v-else>—</span>
              </template>
            </Column>
          </DataTable>
        </TabPanel>
        <TabPanel value="activity">
          <div ref="activityChartEl" class="cmp-chart" />
          <h3 class="cmp-subhead">By activity (Planned / NPT / UPA)</h3>
          <DataTable :value="comparison.by_activity" striped-rows show-gridlines class="bulk-grid-panel">
            <Column field="label" header="Activity" />
            <Column field="activity_code" header="Code" />
            <Column header="Operational charges"><template #body="{ data }">${{ money(data.services_cost) }}</template></Column>
            <Column header="Quantity charges"><template #body="{ data }">${{ money(data.consumables_cost) }}</template></Column>
            <Column header="Total"><template #body="{ data }"><strong>${{ money(data.total_cost) }}</strong></template></Column>
          </DataTable>
          <h3 class="cmp-subhead">By sub-activity (responsible party accountability)</h3>
          <DataTable :value="comparison.by_sub_activity" striped-rows show-gridlines class="bulk-grid-panel">
            <Column field="label" header="Sub-activity" />
            <Column field="activity_name" header="Activity" />
            <Column field="responsible_party" header="Responsible party" />
            <Column header="Operational charges"><template #body="{ data }">${{ money(data.services_cost) }}</template></Column>
            <Column header="Quantity charges"><template #body="{ data }">${{ money(data.consumables_cost) }}</template></Column>
            <Column header="Total"><template #body="{ data }"><strong>${{ money(data.total_cost) }}</strong></template></Column>
          </DataTable>
        </TabPanel>
        <TabPanel value="phase">
          <div ref="phaseChartEl" class="cmp-chart" />
          <DataTable :value="comparison.by_phase" striped-rows show-gridlines class="bulk-grid-panel">
            <Column field="label" header="Phase" />
            <Column header="Planned days"><template #body="{ data }">{{ data.planned_days != null ? Number(data.planned_days).toFixed(1) : '—' }}</template></Column>
            <Column header="Actual days"><template #body="{ data }">{{ data.actual_days != null ? Number(data.actual_days).toFixed(0) : '—' }}</template></Column>
            <Column header="Operational charges"><template #body="{ data }">${{ money(data.services_cost) }}</template></Column>
            <Column header="Quantity charges"><template #body="{ data }">${{ money(data.consumables_cost) }}</template></Column>
            <Column header="Total"><template #body="{ data }"><strong>${{ money(data.total_cost) }}</strong></template></Column>
          </DataTable>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
.cmp-selector-bar {
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
.afe-tags {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.cmp-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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
  font-size: 1.3rem;
  font-weight: 700;
}
.kpi-sub {
  color: var(--text-color-secondary, #64748b);
}
.text-primary { color: var(--primary-color, #0f766e); }
.text-success { color: #16a34a; }
.text-danger { color: #dc2626; }
.cmp-chart {
  width: 100%;
  height: 360px;
  margin: 0.5rem 0 1rem;
}
.cmp-subhead {
  margin: 1.1rem 0 0.5rem;
  font-size: 0.95rem;
}
</style>
