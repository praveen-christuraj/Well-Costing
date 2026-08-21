import { computed, readonly, ref } from 'vue'
import type { ApiClient } from '~/services/apiClient'
import type { HealthResponse } from '~/types/health'

export function useHealth(client: Pick<ApiClient, 'get'> = useApi()) {
  const health = ref<HealthResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isHealthy = computed(
    () => health.value?.status === 'healthy' && health.value.database === 'connected',
  )

  /** The live database is reachable but behind the application's migrations. */
  const isSchemaOutdated = computed(
    () => health.value?.database === 'schema_outdated' || health.value?.schema_status === 'outdated',
  )

  const schemaMessage = computed(() => health.value?.schema_message ?? null)

  async function checkHealth(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      health.value = await client.get<HealthResponse>('/health')
    }
    catch (caught: unknown) {
      health.value = null
      error.value = caught instanceof Error ? caught.message : 'Health check failed'
    }
    finally {
      loading.value = false
    }
  }

  return {
    health: readonly(health),
    loading: readonly(loading),
    error: readonly(error),
    isHealthy,
    isSchemaOutdated,
    schemaMessage,
    checkHealth,
  }
}
