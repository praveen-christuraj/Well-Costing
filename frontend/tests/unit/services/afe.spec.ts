import type { ApiClient } from '~/services/apiClient'
import { AfeApi } from '~/services/afe'

describe('AfeApi', () => {
  it('calls reopen with mandatory remarks', async () => {
    const post = vi.fn().mockResolvedValue({ id: 'afe-1', status: 'draft' })
    const client = { post } as unknown as ApiClient
    const api = new AfeApi(client)

    const res = await api.reopen('afe-1', 'Scope revision for casing section')
    expect(post).toHaveBeenCalledWith('/afes/afe-1/reopen', { remarks: 'Scope revision for casing section' })
    expect(res.status).toBe('draft')
  })

  it('calls drilling phases endpoints', async () => {
    const get = vi.fn().mockResolvedValue([{ code: 'DRILL', name: 'Drilling' }])
    const post = vi.fn().mockResolvedValue({ code: 'LOG', name: 'Logging' })
    const client = { get, post } as unknown as ApiClient
    const api = new AfeApi(client)

    await api.listDrillingPhases()
    expect(get).toHaveBeenCalledWith('/drilling-phases')

    await api.createDrillingPhase({ code: 'LOG', name: 'Logging' })
    expect(post).toHaveBeenCalledWith('/drilling-phases', { code: 'LOG', name: 'Logging' })
  })
})
