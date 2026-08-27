import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

/**
 * Page-level integration test: mounts the real master-data page with a mocked
 * API client and drives the excel-type grid workflow (tab switching, bulk row
 * entry, single bulk save) end to end.
 */

const uomRecords = [
  { id: 1, unit_code: 'M', unit_name: 'Metre', unit_symbol: 'm', description: 'length' },
  { id: 2, unit_code: 'BBL', unit_name: 'Barrel', unit_symbol: 'bbl', description: null },
]

const vendorRecords = [
  { id: 1, vendor_code: 'VEND001', vendor_name: 'Acme Drilling', contact: '+1-555', description: null },
]

const deletedUom = [
  { id: 9, unit_code: 'FT', unit_name: 'Feet', deleted_at: '2026-01-01T00:00:00Z' },
]

type ApiMock = Record<'get' | 'post' | 'put' | 'delete' | 'postForm' | 'download', ReturnType<typeof vi.fn>>

function makeApi(): ApiMock {
  return {
    get: vi.fn((path: string) => {
      if (path === '/master-data/uom') return Promise.resolve(uomRecords)
      if (path === '/master-data/uom/deleted') return Promise.resolve(deletedUom)
      if (path === '/master-data/vendors') return Promise.resolve(vendorRecords)
      if (path === '/master-data/vendors/dropdown') return Promise.resolve([])
      if (path.endsWith('/deleted')) return Promise.resolve([])
      return Promise.resolve([])
    }),
    post: vi.fn().mockResolvedValue({ id: 99 }),
    put: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue(undefined),
    postForm: vi.fn().mockResolvedValue({}),
    download: vi.fn().mockResolvedValue(new Blob()),
  }
}

async function mountPage() {
  vi.resetModules()
  const api = makeApi()
  vi.stubGlobal('definePageMeta', vi.fn())
  vi.stubGlobal('useApi', () => api)

  const component = (await import('~/pages/master-data/index.vue')).default
  const wrapper = mount(component, {
    attachTo: document.body,
  })
  return { wrapper, api }
}

function findTab(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('.tabs__item').find(tab => tab.text().includes(label))
}

function findButton(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('button').find(button => button.text().includes(label))
}

describe('Master data page (excel-type bulk entry)', () => {
  it('renders the generic module grid with loaded records as editable cells', async () => {
    const { wrapper } = await mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('Spreadsheet-style bulk entry')
    expect(findTab(wrapper, 'UOM')?.classes()).toContain('tabs__item--active')

    const values = wrapper.findAll('input').map(input => (input.element as HTMLInputElement).value)
    expect(values).toContain('Metre')
    expect(values).toContain('BBL')
    // Entry forms are gone: no dialog forms, only the grid + toolbar actions.
    expect(wrapper.text()).not.toContain('New Entry')
    expect(findButton(wrapper, 'Save All')).toBeTruthy()
    expect(findButton(wrapper, 'Add row')).toBeTruthy()
    expect(findButton(wrapper, '+5 Rows')).toBeTruthy()
    expect(findButton(wrapper, 'Paste')).toBeTruthy()
  })

  it('supports multi-row entry committed with a single bulk save', async () => {
    const { wrapper, api } = await mountPage()
    await flushPromises()

    await wrapper.findAll('button').find(b => b.text().includes('+5 Rows'))?.trigger('click')
    // UOM rows have 4 cells (code, name, symbol, description); the five new
    // rows sit on top of the table body, so their blank cells come first.
    const blank = wrapper.find('tbody').findAll('input').filter(
      input => (input.element as HTMLInputElement).value === '',
    )
    expect(blank.length).toBeGreaterThanOrEqual(20)
    for (let row = 0; row < 5; row++) {
      await blank[row * 4]?.setValue(`U-${row + 1}`)
      await blank[row * 4 + 1]?.setValue(`Unit ${row + 1}`)
    }

    await wrapper.findAll('button').find(b => b.text().includes('Save All'))?.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledTimes(5)
    expect(api.post).toHaveBeenCalledWith('/master-data/uom', {
      unit_code: 'U-1',
      unit_name: 'Unit 1',
      unit_symbol: 'U-1',
      description: null,
    })
    expect(wrapper.text()).toContain('Saved 5 row(s)')
  })

  it('switches to the vendors grid and saves edits as updates', async () => {
    const { wrapper, api } = await mountPage()
    await flushPromises()

    await findTab(wrapper, 'Vendors/Suppliers')?.trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenCalledWith('/master-data/vendors')

    const nameInput = wrapper.findAll('input').find(
      input => (input.element as HTMLInputElement).value === 'Acme Drilling',
    )
    await nameInput?.setValue('Acme Drilling Services Ltd')
    await wrapper.findAll('button').find(b => b.text().includes('Save All'))?.trigger('click')
    await flushPromises()

    expect(api.put).toHaveBeenCalledWith('/master-data/vendors/1', {
      vendor_code: 'VEND001',
      vendor_name: 'Acme Drilling Services Ltd',
      contact: '+1-555',
      description: null,
    })
  })

  it('shows deleted entries with restore actions', async () => {
    const { wrapper } = await mountPage()
    await flushPromises()

    await findTab(wrapper, 'Deleted Entries')?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Unit of Measurements (UOM)')
    expect(wrapper.text()).toContain('FT')
    expect(wrapper.text()).toContain('Restore')
  })
})
