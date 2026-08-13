import { useHealth } from '~/composables/useHealth'
import type { HealthResponse } from '~/types/health'

describe('useHealth', () => {
  it('reports a healthy API and database', async () => {
    const response: HealthResponse = {
      status: 'healthy',
      database: 'connected',
      environment: 'test',
      version: '0.1.0',
    }
    const get = vi.fn().mockResolvedValue(response)
    const state = useHealth({ get })

    await state.checkHealth()

    expect(get).toHaveBeenCalledWith('/health')
    expect(state.health.value).toEqual(response)
    expect(state.isHealthy.value).toBe(true)
    expect(state.error.value).toBeNull()
    expect(state.loading.value).toBe(false)
  })

  it('normalizes a failed request into composable state', async () => {
    const state = useHealth({ get: vi.fn().mockRejectedValue(new Error('API offline')) })

    await state.checkHealth()

    expect(state.health.value).toBeNull()
    expect(state.isHealthy.value).toBe(false)
    expect(state.error.value).toBe('API offline')
  })
})
