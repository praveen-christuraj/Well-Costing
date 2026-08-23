import { describe, expect, it, vi } from 'vitest'
import { MasterDataApi } from '~/services/masterData'
import type { ApiClient } from '~/services/apiClient'

function stubClient() {
  return {
    get: vi.fn().mockResolvedValue({ cascades: [], requires_confirmation: false }),
    post: vi.fn().mockResolvedValue({}),
    patch: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue(undefined),
  } as unknown as ApiClient
}

describe('MasterDataApi deletion', () => {
  it('asks what a permanent delete would take with it', async () => {
    const client = stubClient()

    await new MasterDataApi(client).deleteImpact('tangibles', 'item-1')

    expect(client.get).toHaveBeenCalledWith('/master-data/tangibles/item-1/delete-impact')
  })

  it('deletes without cascading by default', async () => {
    const client = stubClient()

    await new MasterDataApi(client).remove('tangibles', 'item-1')

    expect(client.delete).toHaveBeenCalledWith('/master-data/tangibles/item-1?hard=true&cascade=false')
  })

  it('cascades the rate history only when the caller confirmed it', async () => {
    const client = stubClient()

    await new MasterDataApi(client).remove('tangibles', 'item-1', true)

    expect(client.delete).toHaveBeenCalledWith('/master-data/tangibles/item-1?hard=true&cascade=true')
  })
})
