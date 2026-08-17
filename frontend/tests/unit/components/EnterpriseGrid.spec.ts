import { flushPromises, mount } from '@vue/test-utils'
import ConfirmationService from 'primevue/confirmationservice'
import PrimeVue from 'primevue/config'
import Tooltip from 'primevue/tooltip'
import type { GridColumn } from '~/types/grid'

const columns: GridColumn[] = [
  { field: 'order_number', header: 'Service order no.' },
  { field: 'contract_value', header: 'Contract value', numeric: true, suffixField: 'currency_code' },
  { field: 'is_active', header: 'Active', type: 'checkbox' },
]

const record = {
  id: 'so-1',
  order_number: 'SO-2026-0001',
  contract_value: 1500,
  currency_code: 'USD',
  is_active: true,
}

type Grid = Awaited<ReturnType<typeof mountGrid>>['wrapper']

async function mountGrid(props: Record<string, unknown> = {}, exportImpl?: ReturnType<typeof vi.fn>) {
  vi.resetModules()

  const exportApi = exportImpl ?? vi.fn().mockResolvedValue(new Blob(['workbook']))
  vi.stubGlobal('useMasterData', () => ({ export: exportApi }))

  const EnterpriseGrid = (await import('~/components/data-grid/EnterpriseGrid.vue')).default
  const wrapper = mount(EnterpriseGrid, {
    props: {
      title: 'Service orders',
      singular: 'service order',
      columns,
      fetchPage: vi.fn().mockResolvedValue({ items: [record], page: 1, page_size: 25, total: 1, pages: 1 }),
      toRow: (item: Record<string, unknown>) => ({ ...item }),
      toPayload: (row: Record<string, unknown>) => ({ ...row }),
      blankRow: () => ({ order_number: '' }),
      bulkCreate: vi.fn(),
      bulkUpdate: vi.fn(),
      removeRecord: vi.fn(),
      ...props,
    },
    global: {
      plugins: [PrimeVue, ConfirmationService],
      directives: { tooltip: Tooltip },
      stubs: { teleport: true },
    },
  })

  await flushPromises()
  return { wrapper, exportApi }
}

function findButton(wrapper: Grid, label: string) {
  return wrapper.findAll('button').find(button => button.text().includes(label))
}

/**
 * Capture the anchor the download helper creates. Only `a` elements are
 * intercepted, so Vue keeps rendering the rest of the grid normally.
 */
function captureDownload() {
  const original = document.createElement.bind(document)
  const anchor = original('a')
  const click = vi.spyOn(anchor, 'click').mockImplementation(() => {})
  const createElement = vi
    .spyOn(document, 'createElement')
    .mockImplementation((tag: string, options?: ElementCreationOptions) =>
      (tag === 'a' ? anchor : original(tag, options)))
  const createObjectURL = vi.fn().mockReturnValue('blob:workbook')
  const revokeObjectURL = vi.fn()
  vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
  return { anchor, click, createElement, createObjectURL, revokeObjectURL }
}

describe('EnterpriseGrid export and print', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('downloads the entity workbook when an export entity is configured', async () => {
    const { wrapper, exportApi } = await mountGrid({ exportEntity: 'service-orders' })
    const download = captureDownload()

    await findButton(wrapper, 'Export')?.trigger('click')
    await flushPromises()

    expect(exportApi).toHaveBeenCalledWith('service-orders')
    expect(download.anchor.download).toBe('service-orders-export.xlsx')
    expect(download.anchor.href).toContain('blob:workbook')
    expect(download.click).toHaveBeenCalledTimes(1)
    // The object URL is released once the click has been dispatched.
    expect(download.revokeObjectURL).toHaveBeenCalledWith('blob:workbook')

    download.createElement.mockRestore()
    expect(wrapper.text()).toContain('Service orders exported to Excel.')
  })

  it('reports a readable message when the export fails', async () => {
    const failing = vi.fn().mockRejectedValue(new Error('Download failed with status 500'))
    const { wrapper } = await mountGrid({ exportEntity: 'purchase-orders' }, failing)

    await findButton(wrapper, 'Export')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('The export failed: Download failed with status 500')
  })

  it('prefers a page-supplied export handler over the built-in download', async () => {
    const onExport = vi.fn().mockResolvedValue(undefined)
    const { wrapper, exportApi } = await mountGrid({ exportEntity: 'service-orders', onExport })

    await findButton(wrapper, 'Export')?.trigger('click')
    await flushPromises()

    expect(onExport).toHaveBeenCalledTimes(1)
    expect(exportApi).not.toHaveBeenCalled()
  })

  it('hides the export button when no export source is configured', async () => {
    const { wrapper } = await mountGrid()

    expect(findButton(wrapper, 'Export')).toBeUndefined()
    expect(findButton(wrapper, 'Print')).toBeDefined()
  })

  it('always offers Print and renders a print-only table of the loaded rows', async () => {
    const print = vi.fn()
    vi.stubGlobal('print', print)

    const { wrapper } = await mountGrid({ exportEntity: 'service-orders' })

    const printTable = wrapper.find('.eg__print-table')
    expect(printTable.exists()).toBe(true)
    // Values print as plain text, with the numeric suffix appended.
    expect(printTable.text()).toContain('SO-2026-0001')
    expect(printTable.text()).toContain('1,500.00 USD')
    // Checkbox columns print a word rather than an input control.
    expect(printTable.text()).toContain('Active')
    expect(printTable.findAll('input')).toHaveLength(0)

    await findButton(wrapper, 'Print')?.trigger('click')
    expect(print).toHaveBeenCalledTimes(1)
  })
})
