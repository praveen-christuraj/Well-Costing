<script setup lang="ts">
/**
 * Landing page for the restructured application.
 *
 * Every business module was removed, so the dashboard reports on the platform
 * itself — API reachability, database connectivity and schema state — and
 * points at the Master Data stub where the rebuilt catalogues will land.
 */
import { computed, onMounted } from 'vue'
import Button from 'primevue/button'
import ErrorState from '~/components/design-system/ErrorState.vue'
import Message from 'primevue/message'
import PageHeader from '~/components/design-system/PageHeader.vue'
import StatCard from '~/components/dashboard/StatCard.vue'
import Tag from 'primevue/tag'

definePageMeta({ middleware: 'auth' })

const { user } = useAuth()
const { health, loading, error, isHealthy, isSchemaOutdated, schemaMessage, checkHealth } = useHealth()

const databaseState = computed(() => health.value?.database ?? 'unknown')
const schemaState = computed(() => health.value?.schema_status ?? 'unknown')

const statTone = computed<'teal' | 'amber'>(() => (isHealthy.value ? 'teal' : 'amber'))

onMounted(() => void checkHealth())
</script>

<template>
  <div class="dashboard-page">
    <PageHeader
      title="Dashboard"
      description="Platform overview — API, database and schema health, plus the catalogues now in Master Data."
    >
      <template #actions>
        <Button
          label="Refresh"
          icon="pi pi-refresh"
          text
          :loading="loading"
          @click="checkHealth"
        />
        <Button
          label="Master Data"
          icon="pi pi-book"
          @click="navigateTo('/master-data')"
        />
      </template>
    </PageHeader>

    <Message v-if="isSchemaOutdated" severity="warn" :closable="false">
      {{ schemaMessage ?? 'Apply the pending database migrations and reload.' }}
    </Message>
    <ErrorState
      v-else-if="error"
      :message="error"
      @retry="checkHealth"
    />

    <section class="dashboard-stats" aria-label="Platform metrics">
      <StatCard
        label="API"
        :value="health?.status ?? 'unknown'"
        icon="pi pi-bolt"
        :tone="statTone"
        :hint="`Environment: ${health?.environment ?? '—'}`"
      />
      <StatCard
        label="Database"
        :value="databaseState"
        icon="pi pi-database"
        :tone="statTone"
        hint="Connectivity reported by /health"
      />
      <StatCard
        label="Schema"
        :value="schemaState"
        icon="pi pi-sitemap"
        :tone="isSchemaOutdated ? 'amber' : 'teal'"
        hint="Migration state"
      />
      <StatCard
        label="Version"
        :value="health?.version ?? '—'"
        icon="pi pi-tag"
        tone="violet"
        :hint="user ? `Signed in as ${user.full_name}` : 'Not signed in'"
      />
    </section>

    <section class="dashboard-widgets">
      <article class="dashboard-widget">
        <header class="dashboard-widget__head">
          <div>
            <h2>Platform status</h2>
            <p>Live values from the backend health endpoint.</p>
          </div>
          <Button
            label="Refresh"
            icon="pi pi-refresh"
            text
            :loading="loading"
            @click="checkHealth"
          />
        </header>
        <div class="dashboard-widget__body">
          <div class="dashboard-status">
            <div>
              <span>API</span>
              <Tag :value="health?.status ?? 'unknown'" :severity="isHealthy ? 'success' : 'warn'" />
            </div>
            <div>
              <span>Database</span>
              <Tag
                :value="databaseState"
                :severity="databaseState === 'connected' ? 'success' : 'warn'"
              />
            </div>
            <div>
              <span>Schema</span>
              <Tag :value="schemaState" :severity="schemaState === 'current' ? 'success' : 'warn'" />
            </div>
          </div>
        </div>
      </article>

      <article class="dashboard-widget">
        <header class="dashboard-widget__head">
          <div>
            <h2>Application state</h2>
            <p>What this build contains after the restructure.</p>
          </div>
        </header>
        <div class="dashboard-widget__body">
          <ol class="dashboard-flow">
            <li>
              <strong>Authentication</strong>
              <span>Sign-in, bearer tokens, users and roles — each sign-in is audit-logged</span>
            </li>
            <li>
              <strong>Master Data</strong>
              <span>UOM, Currencies, Phases, Activities, Hole Sections, Vendors/Suppliers and PO/SO</span>
            </li>
            <li>
              <strong>Audit Log</strong>
              <span>Create, update, delete, restore, import, export and login history</span>
            </li>
          </ol>
        </div>
      </article>
    </section>
  </div>
</template>

<style scoped>
.dashboard-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 14px;
}

.dashboard-widgets {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.dashboard-widget {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}

.dashboard-widget__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--app-border);
}

.dashboard-widget__head h2 {
  margin: 0;
  font-size: .95rem;
}

.dashboard-widget__head p {
  margin: 2px 0 0;
  color: var(--app-muted);
  font-size: .78rem;
}

.dashboard-widget__body {
  padding: 14px 16px;
}

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

.dashboard-flow {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.dashboard-flow li {
  position: relative;
  padding: 8px 0 8px 40px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: #f8fbfc;
  counter-increment: flow;
}

.dashboard-flow {
  counter-reset: flow;
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

.dashboard-flow strong {
  font-size: .85rem;
}

.dashboard-flow span {
  display: block;
  color: var(--app-muted);
  font-size: .78rem;
}

@media (max-width: 1100px) {
  .dashboard-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dashboard-widgets { grid-template-columns: minmax(0, 1fr); }
}

@media (max-width: 560px) {
  .dashboard-stats { grid-template-columns: 1fr; }
}
</style>
