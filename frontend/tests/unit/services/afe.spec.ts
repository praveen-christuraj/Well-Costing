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

  it('follows the same delete procedure for wells and projects', async () => {
    const del = vi.fn().mockResolvedValue(undefined)
    const post = vi.fn().mockResolvedValue({ id: 'well-1', is_active: true })
    const client = { delete: del, post } as unknown as ApiClient
    const api = new AfeApi(client)

    await api.deleteWell('well-1')
    expect(del).toHaveBeenCalledWith('/wells/well-1')

    await api.recoverWell('well-1')
    expect(post).toHaveBeenCalledWith('/wells/well-1/recover', {})

    await api.hardDeleteWell('well-1')
    expect(del).toHaveBeenCalledWith('/wells/well-1/hard')

    await api.recoverProject('proj-1')
    expect(post).toHaveBeenCalledWith('/projects/proj-1/recover', {})

    await api.hardDeleteProject('proj-1')
    expect(del).toHaveBeenCalledWith('/projects/proj-1/hard')
  })

  it('lists removed afe lines and recovers a single line', async () => {
    const get = vi.fn().mockResolvedValue([])
    const post = vi.fn().mockResolvedValue({ id: 'line-1', is_active: true })
    const client = { get, post } as unknown as ApiClient
    const api = new AfeApi(client)

    await api.listRemovedLines('afe-1')
    expect(get).toHaveBeenCalledWith('/afes/afe-1/lines/removed')

    await api.recoverLine('line-1')
    expect(post).toHaveBeenCalledWith('/afe-lines/line-1/recover', {})
  })

  it('filters wells by active state only when requested', async () => {
    const get = vi.fn().mockResolvedValue({ items: [], page: 1, page_size: 500, total: 0, pages: 0 })
    const client = { get } as unknown as ApiClient
    const api = new AfeApi(client)

    await api.listWells()
    expect(get).toHaveBeenCalledWith('/wells?page=1&page_size=500')

    await api.listWells(undefined, false)
    expect(get).toHaveBeenCalledWith('/wells?page=1&page_size=500&is_active=false')
  })
})
