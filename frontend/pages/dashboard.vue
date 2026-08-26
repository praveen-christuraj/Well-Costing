<script setup lang="ts">
/** Dashboard over AFE, AFE Cost Estimates and Daily Cost only. */
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import StatCard from '~/components/dashboard/StatCard.vue'
import EmptyState from '~/components/design-system/EmptyState.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { AfeRecord, WellRecord } from '~/types/afe'
import type { GeneratedReport } from '~/types/reporting'
import { formatMoneyCell } from '~/utils/printDocument'

definePageMeta({ middleware: 'auth' })

const afeApi = useAfe()
const reportingApi = useReporting()
const { health, isHealthy, isSchemaOutdated, schemaMessage, checkHealth } = useHealth()
const afes = ref<AfeRecord[]>([])
const wells = ref<WellRecord[]>([])
const performance = ref<GeneratedReport | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const draftAfes = computed(() => afes.value.filter(afe => afe.status === 'draft'))
const submittedAfes = computed(() => afes.value.filter(afe => afe.status === 'submitted'))
const activeWells = computed(() => wells.value.filter(well => well.status === 'active'))
const recentAfes = computed(() => [...afes.value].slice(0, 6))
const totalActual = computed(() => Number(performance.value?.summaries.find(item => item.key === 'actual')?.value ?? 0))
const totalBudget = computed(() => Number(performance.value?.summaries.find(item => item.key === 'budget')?.value ?? 0))
const performanceRows = computed(() => performance.value?.rows ?? [])

function money(value: string | number | null | undefined): string { return formatMoneyCell(value) }
function wellCode(afe: AfeRecord): string { return afe.well_code || wells.value.find(well => well.id === afe.well_id)?.code || '—' }
function budgetValue(afe: AfeRecord): number { return Number(afe.budget_amount ?? 0) || 0 }

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [afePage, wellPage, report] = await Promise.all([
      afeApi.listAfes(),
      afeApi.listWells(),
      reportingApi.generate({ report_type: 'cost_performance' }),
    ])
    afes.value = afePage.items
    wells.value = wellPage.items
    performance.value = report
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The dashboard could not be loaded.'
  }
  finally { loading.value = false }
  await checkHealth()
}

onMounted(() => void load())
</script>

<template>
  <div class="dashboard-page">
    <PageHeader title="Dashboard" description="Live overview from AFE planning, AFE Cost Estimates and Daily Cost actuals.">
      <template #actions>
        <Button label="Refresh" icon="pi pi-refresh" text :loading="loading" @click="load" />
        <Button label="New AFE" icon="pi pi-plus" @click="navigateTo('/afe')" />
      </template>
    </PageHeader>
    <Message v-if="error" severity="error" closable @close="error = null">{{ error }}</Message>
    <Message v-if="isSchemaOutdated" severity="warn" :closable="false">{{ schemaMessage ?? 'Apply the pending database migrations and reload.' }}</Message>

    <section class="dashboard-stats" aria-label="Headline metrics">
      <StatCard label="AFEs in draft" :value="draftAfes.length" icon="pi pi-file-edit" tone="amber" hint="Still being prepared" />
      <StatCard label="AFEs submitted" :value="submittedAfes.length" icon="pi pi-check-circle" tone="teal" hint="Governing plans" />
      <StatCard label="Active wells" :value="activeWells.length" icon="pi pi-map-marker" tone="blue" :hint="`${wells.length} well(s) registered`" />
      <StatCard label="Daily Cost actual" :value="`$${money(totalActual)}`" icon="pi pi-wallet" tone="violet" :hint="`Budget $${money(totalBudget)}`" />
    </section>

    <section class="dashboard-widgets">
      <article class="dashboard-widget dashboard-widget--wide">
        <header class="dashboard-widget__head">
          <div>
            <h2>Recent AFEs</h2>
            <p>Newest authorisation-for-expenditure plans across every well.</p>
          </div>
          <Button label="Open AFE" icon="pi pi-arrow-right" text @click="navigateTo('/afe')" />
        </header>
        <div class="dashboard-widget__body">
          <DataTable
            :value="recentAfes"
            :loading="loading"
            size="small"
            striped-rows
            scrollable
            scroll-height="flex"
            class="dashboard-widget__table"
          >
            <Column field="code" header="AFE" />
            <Column field="title" header="Title" />
            <Column header="Well"><template #body="{ data }">{{ wellCode(data) }}</template></Column>
            <Column header="Budget"><template #body="{ data }"><strong>${{ money(budgetValue(data)) }}</strong></template></Column>
            <Column field="item_count" header="Lines" />
            <Column header="Status"><template #body="{ data }"><Tag :value="data.status" :severity="data.status === 'submitted' ? 'success' : 'warn'" /></template></Column>
            <template #empty>
              <EmptyState title="No AFEs yet" description="Register a project and well, then create the first AFE." icon="pi pi-clipboard" />
            </template>
          </DataTable>
        </div>
      </article>

      <article class="dashboard-widget dashboard-widget--wide">
        <header class="dashboard-widget__head">
          <div>
            <h2>Well cost performance</h2>
            <p>Budget vs. daily-cost actuals per AFE so you can spot overruns early.</p>
          </div>
          <Button label="Cost Control" icon="pi pi-arrow-right" text @click="navigateTo('/cost-control')" />
        </header>
        <div class="dashboard-widget__body">
          <DataTable
            v-if="performanceRows.length"
            :value="performanceRows"
            size="small"
            striped-rows
            scrollable
            scroll-height="flex"
            class="dashboard-widget__table"
          >
            <Column field="well" header="Well" />
            <Column field="afe" header="AFE" />
            <Column header="Budget"><template #body="{ data }">${{ money(data.budget) }}</template></Column>
            <Column header="Daily actual"><template #body="{ data }"><strong>${{ money(data.actual) }}</strong></template></Column>
            <Column header="Remaining">
              <template #body="{ data }">
                <span :class="Number(data.budget_remaining) < 0 ? 'danger' : 'success'">${{ money(data.budget_remaining) }}</span>
              </template>
            </Column>
          </DataTable>
          <EmptyState
            v-else
            title="No cost performance yet"
            description="AFE and Daily Cost values appear here when wells are configured."
            icon="pi pi-chart-line"
          />
        </div>
      </article>

      <article class="dashboard-widget dashboard-widget--half">
        <header class="dashboard-widget__head">
          <div>
            <h2>Data flow</h2>
            <p>How scope, rates and actuals connect across the platform.</p>
          </div>
        </header>
        <div class="dashboard-widget__body">
          <ol class="dashboard-flow">
            <li>
              <strong>Master Data</strong>
              <span>Classification, cost codes, units and vendors</span>
            </li>
            <li>
              <strong>AFE</strong>
              <span>Well scope, sections, phases, budget and quantities</span>
            </li>
            <li>
              <strong>AFE Cost Estimates</strong>
              <span>Well-scoped rate for every AFE line</span>
            </li>
            <li>
              <strong>Daily Cost &amp; Well Activities</strong>
              <span>Actual spend and accountability</span>
            </li>
          </ol>
        </div>
      </article>

      <article class="dashboard-widget dashboard-widget--half">
        <header class="dashboard-widget__head">
          <div>
            <h2>Platform status</h2>
            <p>Quick health check on the running services.</p>
          </div>
        </header>
        <div class="dashboard-widget__body">
          <div class="dashboard-status">
            <div>
              <span>API</span>
              <Tag :value="health?.status ?? 'unknown'" :severity="isHealthy ? 'success' : 'warn'" />
            </div>
            <div>
              <span>Database</span>
              <Tag :value="health?.database ?? 'unknown'" :severity="health?.database === 'connected' ? 'success' : 'warn'" />
            </div>
            <div>
              <span>Reporting</span>
              <Tag value="Active workflow sources" severity="success" />
            </div>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<style scoped>
.success { color: #16a34a; }
.danger { color: #dc2626; }

.dashboard-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}

.dashboard-widgets {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
  flex: 1 1 auto;
  min-height: 0;
}

.dashboard-widget {
  display: flex;
  flex-direction: column;
  min-height: 320px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-surface);
  box-shadow: var(--app-shadow);
  overflow: hidden;
}

.dashboard-widget--wide { grid-column: span 6; min-height: 360px; }
.dashboard-widget--half { grid-column: span 6; min-height: 280px; }

.dashboard-widget__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--app-border);
  background: linear-gradient(180deg, #fbfdfe, #f5f8fa);
}

.dashboard-widget__head h2 {
  margin: 0;
  font-size: .95rem;
  font-weight: 700;
}

.dashboard-widget__head p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: .78rem;
}

.dashboard-widget__body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  padding: 12px 16px 16px;
  min-height: 0;
}

.dashboard-widget__table {
  flex: 1 1 auto;
  min-height: 0;
}

.dashboard-widget__table :deep(.p-datatable-wrapper) {
  height: 100%;
}

.dashboard-flow {
  display: grid;
  gap: .9rem;
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: flow;
}

.dashboard-flow li {
  position: relative;
  display: grid;
  gap: 2px;
  padding: 10px 12px 10px 40px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: #f8fbfc;
}

.dashboard-flow li::before {
  counter-increment: flow;
  content: counter(flow);
  position: absolute;
  top: 50%;
  left: 12px;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--app-teal);
  color: #fff;
  font-size: .7rem;
  font-weight: 700;
  transform: translateY(-50%);
}

.dashboard-flow strong { font-size: .85rem; }
.dashboard-flow span { color: var(--app-muted); font-size: .78rem; }

.dashboard-status {
  display: grid;
  gap: 10px;
  align-content: start;
}

.dashboard-status > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: #f8fbfc;
  font-size: .82rem;
}

@media (max-width: 1100px) {
  .dashboard-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dashboard-widget--wide,
  .dashboard-widget--half { grid-column: span 12; }
}

@media (max-width: 560px) {
  .dashboard-stats { grid-template-columns: 1fr; }
}
</style>