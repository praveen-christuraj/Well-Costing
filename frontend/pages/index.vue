<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import EmptyState from '~/components/design-system/EmptyState.vue'
import ErrorState from '~/components/design-system/ErrorState.vue'
import LoadingState from '~/components/design-system/LoadingState.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import StatusBadge from '~/components/design-system/StatusBadge.vue'

const { health, loading, error, isHealthy, checkHealth } = useHealth()
let refreshTimer: ReturnType<typeof setInterval> | undefined

const connectionLabel = computed(() => {
  if (loading.value && !health.value) return 'Checking'
  if (isHealthy.value) return 'Connected'
  return 'Unavailable'
})

const connectionTone = computed(() => {
  if (loading.value && !health.value) return 'info' as const
  return isHealthy.value ? 'success' as const : 'danger' as const
})

const comingSoon = [
  {
    title: 'Requirements',
    description: 'Bulk intake of planning requirements without recreating well-design logic.',
    phase: 'Phase 3',
    icon: 'pi pi-clipboard',
  },
  {
    title: 'Cost Library',
    description: 'Version-aware services, materials, equipment, vendors, rates and Excel imports.',
    phase: 'Phase 2',
    icon: 'pi pi-database',
  },
  {
    title: 'Estimates',
    description: 'Auditable estimate versions, server-side calculations and review workflows.',
    phase: 'Phases 4–6',
    icon: 'pi pi-calculator',
  },
  {
    title: 'AFE',
    description: 'Immutable approved budget snapshots with controlled revisions.',
    phase: 'Phase 7',
    icon: 'pi pi-file-check',
  },
]

onMounted(() => {
  void checkHealth()
  refreshTimer = setInterval(() => void checkHealth(), 30_000)
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div class="dashboard-page">
    <PageHeader
      title="Foundation dashboard"
      description="A live view of the application foundation. Business modules remain deliberately locked until their approved phases."
    >
      <template #actions>
        <Button
          label="Refresh status"
          icon="pi pi-refresh"
          severity="secondary"
          outlined
          :loading="loading"
          @click="checkHealth"
        />
      </template>
    </PageHeader>

    <section class="connection-card" aria-labelledby="connection-heading">
      <div class="connection-card__heading">
        <div class="connection-card__icon">
          <i class="pi pi-server" aria-hidden="true" />
        </div>
        <div>
          <span class="section-kicker">Environment readiness</span>
          <h2 id="connection-heading">Backend and database</h2>
        </div>
        <StatusBadge
          class="connection-card__status"
          :label="connectionLabel"
          :tone="connectionTone"
          :icon="isHealthy ? 'pi pi-check-circle' : 'pi pi-times-circle'"
        />
      </div>

      <LoadingState v-if="loading && !health" message="Checking API and database connectivity…" />
      <ErrorState
        v-else-if="error"
        title="Backend is not reachable"
        :message="error"
        @retry="checkHealth"
      />
      <div v-else-if="health" class="connection-metrics">
        <div>
          <span>API</span>
          <strong>{{ health.status === 'healthy' ? 'Operational' : 'Degraded' }}</strong>
        </div>
        <div>
          <span>PostgreSQL</span>
          <strong>{{ health.database }}</strong>
        </div>
        <div>
          <span>Environment</span>
          <strong>{{ health.environment }}</strong>
        </div>
        <div>
          <span>API version</span>
          <strong>v{{ health.version }}</strong>
        </div>
      </div>
    </section>

    <section aria-labelledby="modules-heading">
      <div class="section-heading">
        <div>
          <span class="section-kicker">Delivery roadmap</span>
          <h2 id="modules-heading">Business modules</h2>
        </div>
        <span>Bulk-first by design</span>
      </div>
      <div class="module-grid">
        <Card v-for="module in comingSoon" :key="module.title" class="module-card">
          <template #content>
            <EmptyState
              :title="module.title"
              :description="module.description"
              :icon="module.icon"
            >
              <template #action>
                <StatusBadge :label="`Coming in ${module.phase}`" tone="info" />
              </template>
            </EmptyState>
          </template>
        </Card>
      </div>
    </section>

    <section class="principles-strip" aria-label="Architecture principles">
      <div>
        <i class="pi pi-table" aria-hidden="true" />
        <span><strong>Bulk first</strong> Grid, paste and Excel workflows</span>
      </div>
      <div>
        <i class="pi pi-history" aria-hidden="true" />
        <span><strong>Auditable</strong> Versions and source lineage</span>
      </div>
      <div>
        <i class="pi pi-sitemap" aria-hidden="true" />
        <span><strong>Layered</strong> Business logic stays in the domain</span>
      </div>
    </section>
  </div>
</template>
