import type { ApiClient } from '~/services/apiClient'
import { AfeEstimatesApi } from '~/services/afeEstimates'

describe('AfeEstimatesApi', () => {
  it('uses only the current submitted-AFE estimate routes', async () => {
    const get = vi.fn().mockResolvedValue({ afe_id: 'afe-1', lines: [] })
    const put = vi.fn().mockResolvedValue({ afe_id: 'afe-1', lines: [] })
    const post = vi.fn().mockResolvedValue(undefined)
    const download = vi.fn().mockResolvedValue(new Blob())
    const api = new AfeEstimatesApi({ get, put, post, download } as unknown as ApiClient)

    await api.get('afe-1')
    await api.saveRates('afe-1', [{ afe_line_id: 'line-1', unit_rate: 500 }])
    await api.recordPrint('afe-1')
    await api.export('afe-1')

    expect(get).toHaveBeenCalledWith('/afes/afe-1/cost-estimate')
    expect(put).toHaveBeenCalledWith('/afes/afe-1/cost-estimate/rates', {
      rates: [{ afe_line_id: 'line-1', unit_rate: 500 }],
    })
    expect(post).toHaveBeenCalledWith('/afes/afe-1/cost-estimate/audit/print', {})
    expect(download).toHaveBeenCalledWith('/afes/afe-1/cost-estimate/export')
  })
})
