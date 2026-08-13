import type { ApiClient } from '~/services/apiClient'
import { AssuranceApi } from '~/services/assurance'

describe('AssuranceApi', () => {
  it('uses the authenticated assurance status boundary', async () => {
    const get = vi.fn().mockResolvedValue({ status: 'framework_ready' })
    const api = new AssuranceApi({ get } as unknown as ApiClient)
    await api.status()
    expect(get).toHaveBeenCalledWith('/assurance/status')
  })
})
