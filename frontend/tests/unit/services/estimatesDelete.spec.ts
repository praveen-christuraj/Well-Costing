import type { ApiClient } from '~/services/apiClient'
import { EstimateApi } from '~/services/estimates'

describe('EstimateApi delete procedure', () => {
  it('soft deletes, recovers, and permanently deletes an estimate', async () => {
    const del = vi.fn().mockResolvedValue(undefined)
    const post = vi.fn().mockResolvedValue({ id: 'est-1', is_active: true })
    const client = { delete: del, post } as unknown as ApiClient
    const api = new EstimateApi(client)

    await api.delete('est-1')
    expect(del).toHaveBeenCalledWith('/estimates/est-1')

    await api.recover('est-1')
    expect(post).toHaveBeenCalledWith('/estimates/est-1/recover', {})

    await api.hardDelete('est-1')
    expect(del).toHaveBeenCalledWith('/estimates/est-1/hard')
  })

  it('lists active estimates by default and deleted when asked', async () => {
    const get = vi.fn().mockResolvedValue({ items: [], page: 1, page_size: 500, total: 0, pages: 0 })
    const client = { get } as unknown as ApiClient
    const api = new EstimateApi(client)

    await api.list()
    expect(get).toHaveBeenCalledWith('/estimates?page=1&page_size=500&is_active=true')

    await api.list(null)
    expect(get).toHaveBeenCalledWith('/estimates?page=1&page_size=500')

    await api.list(false)
    expect(get).toHaveBeenCalledWith('/estimates?page=1&page_size=500&is_active=false')
  })
})
