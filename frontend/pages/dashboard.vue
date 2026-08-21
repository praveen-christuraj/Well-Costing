<script setup lang="ts">
/**
 * Dashboard — the overview the app opens on.
 *
 * Widgets are laid out on a twelve-column grid after the PrimeVue Sakai
 * dashboard, and every figure comes from a real endpoint: AFEs and wells from
 * the AFE API, cost states from the reporting contract, and the API/database
 * status from the health check. Figures the costing rules do not yet produce
 * are shown as pending rather than invented.
 */
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
import type { Estimate } from '~/types/estimates'
import type { CostOverviewReport } from '~/types/reporting'

definePageMeta({ middleware: 'auth' })

const afeApi = useAfe()
const estimateApi = useEstimates()
const reportingApi = useReporting()
const { health, isHealthy, isSchemaOutdated, schemaMessage, checkHealth } = useHealth()

const afes = ref<AfeRecord[]>([])
const wells = ref<WellRecord[]>([])
const estimates = ref<Estimate[]>([])
const report = ref<CostOverviewReport | null>(null)

const loading = ref(false)
const error = ref<string | null>(null)

const draftAfes = computed(() => afes.value.filter(afe => afe.status === 'draft'))
const submittedAfes = computed(() => afes.value.filter(afe => afe.status === 'submitted'))
const activeWells = computed(() => wells.value.filter(well => well.status === 'active'))
const totalLines = computed(() => afes.value.reduce((sum, afe) => sum + afe.item_count, 0))

/** The most recently touched AFEs, newest first, capped for the widget. */
const recentAfes = computed(() => [...afes.value].slice(0, 6))

const stateSummaries = computed(() => report.value?.state_summaries ?? [])
const pendingMetrics = computed(() => report.value?.pending_metrics ?? [])

function statusSeverity(status: string): string {
  return status === 'submitted' ? 'success' : 'warn'
}

function wellCode(afe: AfeRecord): string {
  return afe.well_code || wells.value.find(well => well.id === afe.well_id)?.code || '—'
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [afePage, wellPage, estimatePage] = await Promise.all([
      afeApi.listAfes(),
      afeApi.listWells(),
      estimateApi.list(),
    ])
    afes.value = afePage.items
    wells.value = wellPage.items
    estimates.value = estimatePage.items
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The dashboard could not be loaded.'
  }
  finally {
    loading.value = false
  }

  // The reporting contract is policy-pending, so a failure here is expected
  // and must not take the rest of the dashboard down with it.
  try {
    report.value = await reportingApi.overview({})
  }
  catch {
    report.value = null
  }
  await checkHealth()
}

onMounted(() => void load())
</script>

<template>
  <div class="dashboard-page">
    <PageHeader
      title="Dashboard"
      description="Where the well cost programme stands today: AFEs in preparation, cost builds under way, and the cost states posted so far."
    >
      <template #actions>
        <Button label="Refresh" icon="pi pi-refresh" text :loading="loading" @click="load" />
        <Button label="New AFE" icon="pi pi-plus" @click="navigateTo('/afe')" />
      </template>
    </PageHeader>

    <Message v-if="error" severity="error" :closable="true" @close="error = null">{{ error }}</Message>

    <Message v-if="isSchemaOutdated" severity="warn" :closable="false">
      {{ schemaMessage ?? 'The database schema is behind the application code — apply the pending migrations and reload.' }}
    </Message>

    <div class="dashboard-grid">
      <div class="dashboard-col dashboard-col--3">
        <StatCard label="AFEs in draft" :value="draftAfes.length" icon="pi pi-file-edit" tone="amber" hint="Still being prepared" />
      </div>
      <div class="dashboard-col dashboard-col--3">
        <StatCard label="AFEs submitted" :value="submittedAfes.length" icon="pi pi-check-circle" tone="teal" hint="Ready for a cost build" />
      </div>
      <div class="dashboard-col dashboard-col--3">
        <StatCard label="Active wells" :value="activeWells.length" icon="pi pi-map-marker" tone="blue" :hint="`${wells.length} well(s) registered`" />
      </div>
      <div class="dashboard-col dashboard-col--3">
        <StatCard label="Cost builds" :value="estimates.length" icon="pi pi-calculator" tone="violet" :hint="`${totalLines} AFE line(s) planned`" />
      </div>

      <section class="dashboard-col dashboard-col--8 dashboard-card">
        <header class="dashboard-card__header">
          <h2>Recent AFEs</h2>
          <Button label="Open AFE workspace" icon="pi pi-arrow-right" icon-pos="right" text size="small" @click="navigateTo('/afe')" />
        </header>
        <DataTable :value="recentAfes" :loading="loading" data-key="id" size="small" striped-rows>
          <Column field="code" header="Code" />
          <Column field="title" header="Title" />
          <Column header="Well">
            <template #body="{ data }">{{ wellCode(data) }}</template>
          </Column>
          <Column field="item_count" header="Lines" />
          <Column header="Status">
            <template #body="{ data }">
              <Tag :value="data.status" :severity="statusSeverity(data.status)" />
            </template>
          </Column>
          <template #empty>
            <EmptyState
              title="No AFEs yet"
              description="Register a project and well, then raise the first AFE to see it here."
              icon="pi pi-clipboard"
            />
          </template>
        </DataTable>
      </section>

      <section class="dashboard-col dashboard-col--4 dashboard-card">
        <header class="dashboard-card__header">
          <h2>Cost states</h2>
          <Button label="Reports" icon="pi pi-chart-bar" text size="small" @click="navigateTo('/reports')" />
        </header>
        <ul v-if="stateSummaries.length" class="dashboard-states">
          <li v-for="summary in stateSummaries" :key="summary.cost_state">
            <span class="dashboard-states__name">{{ summary.cost_state.replace('_', ' ') }}</span>
            <span class="dashboard-states__count">{{ summary.transaction_count }} txn</span>
            <strong class="dashboard-states__amount">{{ summary.amount ?? 'Pending' }}</strong>
          </li>
        </ul>
        <EmptyState
          v-else
          title="No posted cost yet"
          description="Cost states appear once transactions are posted through Cost Control."
          icon="pi pi-arrow-right-arrow-left"
        />
      </section>

      <section class="dashboard-col dashboard-col--6 dashboard-card">
        <header class="dashboard-card__header">
          <h2>Platform status</h2>
        </header>
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
            <span>Reporting contract</span>
            <Tag :value="report?.policy_version ?? 'unavailable'" severity="info" />
          </div>
        </div>
      </section>

      <section class="dashboard-col dashboard-col--6 dashboard-card">
        <header class="dashboard-card__header">
          <h2>Pending policy</h2>
        </header>
        <p class="dashboard-note">
          These figures stay blank on purpose: the rules behind them have not been confirmed,
          and the app refuses to guess a financial number.
        </p>
        <ul v-if="pendingMetrics.length" class="dashboard-pending">
          <li v-for="metric in pendingMetrics" :key="metric">{{ metric }}</li>
        </ul>
        <EmptyState
          v-else
          title="Nothing pending to report"
          description="The reporting contract could not be read, or every metric is confirmed."
          icon="pi pi-info-circle"
        />
      </section>
    </div>
  </div>
</template>
