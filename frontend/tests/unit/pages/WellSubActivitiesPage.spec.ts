import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Select from 'primevue/select'

/**
 * Page-level test for Well Sub Activities: the page is completely well scoped
 * (rig → well context first, then the bulk grid loads only that well's sub
 * activities), carries the common template (Import / XLSX / CSV / Print) and
 * the Deleted Entries tab restores or permanently deletes per well.
 */

const rigs = [
  { id: 1, rig_code: 'RIG001', rig_name: 'Drilling Rig Alpha', display_name: 'RIG001 - Drilling Rig Alpha' },
  { id: 2, rig_code: 'RIG002', rig_name: 'Drilling Rig Bravo', display_name: 'RIG002 - Drilling Rig Bravo' },
]

const wells = [
  { id: 1, rig_id: 1, well_code: 'WELL001', well_name: 'Exploratory 1', status: 'active' },
  { id: 2, rig_id: 1, well_code: 'WELL002', well_name: 'Development 2', status: 'active' },
  { id: 3, rig_id: 2, well_code: 'WELL003', well_name: 'Appraisal 3', status: 'active' },
]

const activities = [
  { id: 11, activity_code: 'DRL', activity_name: 'Drilling' },
  { id: 12, activity_code: 'TST', activity_name: 'Testing' },
]

const subActivityRows = [
  {
    id: 21,
    well_id: 1,
    sub_activity_code: 'RIH-01',
    sub_activity_name: 'Run in hole',
    activity_id: 11,
    responsible_party: 'Schlumberger',
    description: 'RIH with tubing',
    activity_code: 'DRL',
    activity_name: 'Drilling',
    activity_display: 'DRL - Drilling',
  },
]

const deletedRows = [
  {
    id: 22,
    well_id: 1,
    sub_activity_code: 'TEST-01',
    sub_activity_name: 'Well testing',
    activity_id: 12,
    responsible_party: 'Halliburton',
    description: 'Flow test',
    is_deleted: true,
    deleted_at: '2026-08-29T09:00:00Z',
    activity_code: 'TST',
    activity_name: 'Testing',
    activity_display: 'TST - Testing',
  },
]

type ApiMock = Record<'get' | 'post' | 'put' | 'delete' | 'download', ReturnType<typeof vi.fn>>

function makeApi(): ApiMock {
  return {
    get: vi.fn((path: string) => {
      if (path === '/rig-well/rigs/dropdown') return Promise.resolve(rigs)
      if (path === '/rig-well/wells') return Promise.resolve(wells)
      if (path === '/master-data/activities') return Promise.resolve(activities)
      if (path.startsWith('/well-sub-activities?')) return Promise.resolve(subActivityRows)
      if (path.startsWith('/well-sub-activities/deleted')) return Promise.resolve(deletedRows)
      return Promise.resolve([])
    }),
    post: vi.fn().mockResolvedValue({}),
    put: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue(undefined),
    download: vi.fn().mockResolvedValue(new Blob()),
  }
}

async function mountPage() {
  vi.resetModules()
  const api = makeApi()
  vi.stubGlobal('definePageMeta', vi.fn())
  vi.stubGlobal('useApi', () => api)

  const component = (await import('~/pages/well-sub-activities/index.vue')).default
  const wrapper = mount(component, { attachTo: document.body })
  await flushPromises()
  return { wrapper, api }
}

function contextSelects(wrapper: ReturnType<typeof mount>) {
  return wrapper.find('.context-card').findAllComponents(Select)
}

async function pickWellContext(wrapper: ReturnType<typeof mount>, rigId = 1, wellId = 1) {
  const [rigSelect, wellSelect] = contextSelects(wrapper)
  rigSelect.vm.$emit('update:model-value', rigId)
  await flushPromises()
  const [, wellSelectAfter] = contextSelects(wrapper)
  ;(wellSelectAfter ?? wellSelect).vm.$emit('update:model-value', wellId)
  await flushPromises()
}

function findTab(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('.tabs__item').find(tab => tab.text().includes(label))
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('Well Sub Activities — well scope', () => {
  it('asks for the rig and well before any data entry', async () => {
    const { wrapper } = await mountPage()
    expect(wrapper.find('.context-card').exists()).toBe(true)
    expect(wrapper.find('[data-testid="excel-grid"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Select the rig and the corresponding well above')
    wrapper.unmount()
  })

  it('filters the well dropdown to the selected rig', async () => {
    const { wrapper } = await mountPage()
    const [rigSelect] = contextSelects(wrapper)
    rigSelect.vm.$emit('update:model-value', 2)
    await flushPromises()

    const [, wellSelect] = contextSelects(wrapper)
    const options = wellSelect.props('options') as Array<{ id: number, rig_id: number }>
    expect(options.map(option => option.id)).toEqual([3])
    wrapper.unmount()
  })

  it('loads the grid with only the selected well’s sub activities', async () => {
    const { wrapper, api } = await mountPage()
    await pickWellContext(wrapper)

    expect(api.get).toHaveBeenCalledWith('/well-sub-activities?well_id=1')
    const grid = wrapper.find('[data-testid="excel-grid"]')
    expect(grid.exists()).toBe(true)
    expect(grid.text()).toContain('RIH-01')
    expect(grid.text()).toContain('Schlumberger')
    expect(wrapper.text()).toContain('Entering sub activities for')
    expect(wrapper.text()).toContain('WELL001 - Exploratory 1')
    wrapper.unmount()
  })

  it('carries Import, XLSX, CSV and Print on the entry tab', async () => {
    const { wrapper } = await mountPage()
    await pickWellContext(wrapper)
    const labels = wrapper.findAll('button').map(button => button.text())
    for (const expected of ['Import', 'XLSX', 'CSV', 'Print', 'Save All', 'Add row']) {
      expect(labels.some(label => label.includes(expected))).toBe(true)
    }
    wrapper.unmount()
  })

  it('exports scoped to the selected well', async () => {
    const { wrapper, api } = await mountPage()
    await pickWellContext(wrapper)
    const xlsxButton = wrapper.findAll('button').find(button => button.text().includes('XLSX'))
    await xlsxButton?.trigger('click')
    await flushPromises()
    expect(api.download).toHaveBeenCalledWith('/well-sub-activities/export?format=xlsx&well_id=1')
    wrapper.unmount()
  })

  it('shows the two tabs once a well is selected', async () => {
    const { wrapper } = await mountPage()
    await pickWellContext(wrapper)
    const labels = wrapper.findAll('.tabs__item').map(tab => tab.text().trim())
    expect(labels).toEqual(['Well Sub Activities', 'Deleted Entries'])
    expect(findTab(wrapper, 'Deleted Entries')?.classes()).toContain('tabs__item--danger')
    wrapper.unmount()
  })
})

describe('Well Sub Activities — deleted entries', () => {
  it('lists deleted entries of the selected well and restores them', async () => {
    const { wrapper, api } = await mountPage()
    await pickWellContext(wrapper)

    await findTab(wrapper, 'Deleted Entries')?.trigger('click')
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith('/well-sub-activities/deleted?well_id=1')
    const table = wrapper.find('.trash-table').text()
    expect(table).toContain('TEST-01')
    expect(table).toContain('Halliburton')
    expect(table).toContain('TST - Testing')

    const restoreButton = wrapper.findAll('tbody tr')[0]
      ?.findAll('button')
      .find(button => button.text().includes('Restore'))
    await restoreButton?.trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/well-sub-activities/22/restore', {})
    wrapper.unmount()
  })
})
