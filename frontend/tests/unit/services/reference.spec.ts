import { describe, expect, it, vi } from 'vitest'
import { ReferenceApi } from '~/services/reference'
import type { ApiClient } from '~/services/apiClient'

function stubClient() {
  return {
    get: vi.fn().mockResolvedValue({ slot: 'afe.line.item', source: 'catalog.all', total: 0, options: [] }),
    put: vi.fn().mockResolvedValue({}),
    deleteJson: vi.fn().mockResolvedValue({}),
  } as unknown as ApiClient
}

describe('ReferenceApi', () => {
  it('reads the whole registry, or one module of it', async () => {
    const client = stubClient()
    const api = new ReferenceApi(client)

    await api.registry()
    await api.registry('afe')

    expect(client.get).toHaveBeenNthCalledWith(1, '/reference/registry')
    expect(client.get).toHaveBeenNthCalledWith(2, '/reference/registry?module=afe')
  })

  it('resolves options for a slot, passing the cascade parent through', async () => {
    const client = stubClient()

    await new ReferenceApi(client).options('afe.line.secondary_category', { parent_id: 'primary-1' })

    expect(client.get).toHaveBeenCalledWith(
      '/reference/options/afe.line.secondary_category?parent_id=primary-1',
    )
  })

  it('omits unset cascade parameters so the slot returns its full list', async () => {
    const client = stubClient()

    await new ReferenceApi(client).options('daily_cost.service_item', {
      parent_id: undefined,
      well_id: null,
    })

    expect(client.get).toHaveBeenCalledWith('/reference/options/daily_cost.service_item?')
  })

  it('binds and resets a slot through the administrator endpoints', async () => {
    const client = stubClient()
    const api = new ReferenceApi(client)

    await api.bind('daily_cost.service_item', { source_code: 'catalog.tangibles' })
    await api.reset('daily_cost.service_item')

    expect(client.put).toHaveBeenCalledWith('/reference/slots/daily_cost.service_item', {
      source_code: 'catalog.tangibles',
    })
    expect(client.deleteJson).toHaveBeenCalledWith('/reference/slots/daily_cost.service_item')
  })
})
