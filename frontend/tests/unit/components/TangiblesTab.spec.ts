import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ExcelGrid from '~/components/master-data/ExcelGrid.vue'
import TangiblesTab from '~/components/catalogue/TangiblesTab.vue'

/**
 * The Tangibles tab opts the shared grid into the relaxed duplicate rule:
 * names may repeat when manufacturer / rate / uplift / description differ.
 * The prop must arrive as a real array (a string attribute would break
 * Save All), so assert the exact value the grid receives.
 */
describe('TangiblesTab', () => {
  it('passes the duplicate-name key fields to the grid as an array', async () => {
    const api = {
      get: vi.fn((path: string) => {
        if (path === '/master-data/currencies') return Promise.resolve([])
        if (path === '/master-data/uom') return Promise.resolve([])
        if (path === '/catalogue/tangibles/dropdown-options') {
          return Promise.resolve({ categories: [], subcategories: [], manufacturers: [] })
        }
        return Promise.resolve([])
      }),
      post: vi.fn().mockResolvedValue({ id: 99 }),
      put: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue(undefined),
      postForm: vi.fn().mockResolvedValue({}),
      download: vi.fn().mockResolvedValue(new Blob()),
    }
    vi.stubGlobal('useApi', () => api)

    const wrapper = mount(TangiblesTab)
    await flushPromises()

    const grid = wrapper.findComponent(ExcelGrid)
    expect(grid.exists()).toBe(true)
    expect(grid.props('duplicateKeyFields')).toEqual([
      'manufacturer',
      'unit_rate_po',
      'cost_uplift',
      'description',
    ])
  })
})
