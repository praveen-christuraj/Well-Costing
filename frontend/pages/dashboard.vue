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
const performanceRows = computed(() => performance.value?.rows ?? [])

function money(value: string | number | null | undefined): string { return formatMoneyCell(value) }
function wellCode(afe: AfeRecord): string { return afe.well_code || wells.value.find(well => well.id === afe.well_id)?.code || '—' }

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
      <template #actions><Button label="Refresh" icon="pi pi-refresh" text :loading="loading" @click="load" /><Button label="New AFE" icon="pi pi-plus" @click="navigateTo('/afe')" /></template>
    </PageHeader>
    <Message v-if="error" severity="error" closable @close="error = null">{{ error }}</Message>
    <Message v-if="isSchemaOutdated" severity="warn" :closable="false">{{ schemaMessage ?? 'Apply the pending database migrations and reload.' }}</Message>

    <div class="dashboard-grid">
      <div class="dashboard-col dashboard-col--3"><StatCard label="AFEs in draft" :value="draftAfes.length" icon="pi pi-file-edit" tone="amber" hint="Still being prepared" /></div>
      <div class="dashboard-col dashboard-col--3"><StatCard label="AFEs submitted" :value="submittedAfes.length" icon="pi pi-check-circle" tone="teal" hint="Governing plans" /></div>
      <div class="dashboard-col dashboard-col--3"><StatCard label="Active wells" :value="activeWells.length" icon="pi pi-map-marker" tone="blue" :hint="`${wells.length} well(s) registered`" /></div>
      <div class="dashboard-col dashboard-col--3"><StatCard label="Daily Cost actual" :value="`$${money(totalActual)}`" icon="pi pi-wallet" tone="violet" hint="Across active wells" /></div>

      <section class="dashboard-col dashboard-col--7 dashboard-card">
        <header class="dashboard-card__header"><h2>Recent AFEs</h2><Button label="Open AFE" icon="pi pi-arrow-right" text @click="navigateTo('/afe')" /></header>
        <DataTable :value="recentAfes" :loading="loading" size="small" striped-rows><Column field="code" header="AFE" /><Column field="title" header="Title" /><Column header="Well"><template #body="{ data }">{{ wellCode(data) }}</template></Column><Column field="item_count" header="Lines" /><Column header="Status"><template #body="{ data }"><Tag :value="data.status" :severity="data.status === 'submitted' ? 'success' : 'warn'" /></template></Column><template #empty><EmptyState title="No AFEs yet" description="Register a project and well, then create the first AFE." icon="pi pi-clipboard" /></template></DataTable>
      </section>

      <section class="dashboard-col dashboard-col--5 dashboard-card">
        <header class="dashboard-card__header"><h2>Well cost performance</h2><Button label="Cost Control" icon="pi pi-arrow-right" text @click="navigateTo('/cost-control')" /></header>
        <DataTable v-if="performanceRows.length" :value="performanceRows" size="small" striped-rows><Column field="well" header="Well" /><Column field="afe" header="AFE" /><Column header="Budget"><template #body="{ data }">${{ money(data.budget) }}</template></Column><Column header="Daily actual"><template #body="{ data }"><strong>${{ money(data.actual) }}</strong></template></Column><Column header="Remaining"><template #body="{ data }"><span :class="Number(data.budget_remaining) < 0 ? 'danger' : 'success'">${{ money(data.budget_remaining) }}</span></template></Column></DataTable>
        <EmptyState v-else title="No cost performance yet" description="AFE and Daily Cost values appear here when wells are configured." icon="pi pi-chart-line" />
      </section>

      <section class="dashboard-col dashboard-col--6 dashboard-card"><header class="dashboard-card__header"><h2>Data flow</h2></header><ol class="dashboard-flow"><li><strong>Master Data</strong><span>Classification, cost codes, units and vendors</span></li><li><strong>AFE</strong><span>Well scope, sections, phases, budget and quantities</span></li><li><strong>AFE Cost Estimates</strong><span>Well-scoped rate for every AFE line</span></li><li><strong>Daily Cost & Well Activities</strong><span>Actual spend and accountability</span></li></ol></section>
      <section class="dashboard-col dashboard-col--6 dashboard-card"><header class="dashboard-card__header"><h2>Platform status</h2></header><div class="dashboard-status"><div><span>API</span><Tag :value="health?.status ?? 'unknown'" :severity="isHealthy ? 'success' : 'warn'" /></div><div><span>Database</span><Tag :value="health?.database ?? 'unknown'" :severity="health?.database === 'connected' ? 'success' : 'warn'" /></div><div><span>Reporting</span><Tag value="Active workflow sources" severity="success" /></div></div></section>
    </div>
  </div>
</template>

<style scoped>
.success { color: #16a34a; } .danger { color: #dc2626; }
.dashboard-flow { display: grid; gap: .75rem; padding-left: 1.2rem; }
.dashboard-flow li { padding-left: .25rem; } .dashboard-flow strong, .dashboard-flow span { display: block; } .dashboard-flow span { color: var(--text-color-secondary); font-size: .85rem; margin-top: .15rem; }
</style>
