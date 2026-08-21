import type { ApiClient } from '~/services/apiClient'
import { DailyCostApi } from '~/services/dailyCost'

describe('DailyCostApi', () => {
  it('calls daily cost endpoints with correct paths and payloads', async () => {
    const get = vi.fn().mockResolvedValue({ well_id: 'well-1' })
    const post = vi.fn().mockResolvedValue({ id: 'entry-1' })
    const del = vi.fn().mockResolvedValue(undefined)
    const client = { get, post, delete: del } as unknown as ApiClient
    const api = new DailyCostApi(client)

    await api.listEntries('well-1')
    expect(get).toHaveBeenCalledWith('/wells/well-1/daily-cost')

    await api.getEntry('well-1', '2026-08-21')
    expect(get).toHaveBeenCalledWith('/wells/well-1/daily-cost/entry?entry_date=2026-08-21')

    await api.saveEntry('well-1', { entry_date: '2026-08-21', services: [] })
    expect(post).toHaveBeenCalledWith('/wells/well-1/daily-cost', { entry_date: '2026-08-21', services: [] })

    await api.deleteEntry('well-1', 'entry-1')
    expect(del).toHaveBeenCalledWith('/wells/well-1/daily-cost/entry-1')

    await api.getAnalytics('well-1')
    expect(get).toHaveBeenCalledWith('/wells/well-1/daily-cost/analytics')

    await api.getReferenceRates('well-1')
    expect(get).toHaveBeenCalledWith('/wells/well-1/daily-cost/reference-rates')
  })
})
