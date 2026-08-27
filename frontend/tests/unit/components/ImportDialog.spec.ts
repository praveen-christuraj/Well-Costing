import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ImportDialog from '~/components/master-data/ImportDialog.vue'

/**
 * Regression tests for the master-data bulk import dialog: it must actually
 * open (the PrimeVue visibility binding), offer the template download, and
 * upload the selected file to the given endpoint. The PrimeVue Dialog is
 * teleported to document.body, so assertions query the body directly.
 */

type ApiMock = Record<'get' | 'post' | 'put' | 'delete' | 'postForm' | 'download', ReturnType<typeof vi.fn>>

function makeApi(): ApiMock {
  return {
    get: vi.fn().mockResolvedValue([]),
    post: vi.fn().mockResolvedValue({}),
    put: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue(undefined),
    postForm: vi.fn().mockResolvedValue({ imported_count: 2, error_count: 0, errors: [] }),
    download: vi.fn().mockResolvedValue(new Blob(['template'], { type: 'application/octet-stream' })),
  }
}

function mountDialog(api: ApiMock, props: Record<string, unknown> = {}) {
  vi.stubGlobal('useApi', () => api)
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: vi.fn(() => 'blob:mock'),
    revokeObjectURL: vi.fn(),
  })
  return mount(ImportDialog, {
    attachTo: document.body,
    props: {
      visible: true,
      title: 'Bulk Import Units (CSV / XLSX)',
      endpoint: '/master-data/uom/import',
      templateEndpoint: '/master-data/uom/import-template',
      templateFilename: 'uom_template.xlsx',
      ...props,
    },
  })
}

function bodyFind(selector: string): HTMLElement | null {
  return document.body.querySelector(selector)
}

async function selectFile(file: File) {
  const input = bodyFind('input[type="file"]') as HTMLInputElement
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  input.dispatchEvent(new Event('change'))
  await flushPromises()
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('ImportDialog', () => {
  it('opens and shows the template download + upload steps', async () => {
    const api = makeApi()
    const wrapper = mountDialog(api)
    await flushPromises()
    expect(document.body.textContent).toContain('Bulk Import Units')
    expect(document.body.textContent).toContain('Download the template')
    expect(bodyFind('[data-testid="download-template"]')).toBeTruthy()
    expect(bodyFind('[data-testid="import-file-input"]')).toBeTruthy()
    const importButton = bodyFind('[data-testid="execute-import"]') as HTMLButtonElement
    expect(importButton).toBeTruthy()
    expect(importButton.disabled).toBe(true)
    wrapper.unmount()
  })

  it('downloads the template from the backend endpoint', async () => {
    const api = makeApi()
    const wrapper = mountDialog(api)
    await flushPromises()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    ;(bodyFind('[data-testid="download-template"]') as HTMLButtonElement).click()
    await flushPromises()
    expect(api.download).toHaveBeenCalledWith('/master-data/uom/import-template')
    expect(clickSpy).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('rejects unsupported file types with a friendly error', async () => {
    const api = makeApi()
    const wrapper = mountDialog(api)
    await flushPromises()
    await selectFile(new File(['data'], 'records.pdf', { type: 'application/pdf' }))
    expect(bodyFind('[data-testid="import-error"]')?.textContent).toContain('not supported')
    const importButton = bodyFind('[data-testid="execute-import"]') as HTMLButtonElement
    expect(importButton.disabled).toBe(true)
    wrapper.unmount()
  })

  it('uploads the selected file and reports the import summary', async () => {
    const api = makeApi()
    const wrapper = mountDialog(api)
    await flushPromises()
    await selectFile(new File(['unit_code,unit_name\nm,Metre'], 'uom_template.xlsx'))
    const importButton = bodyFind('[data-testid="execute-import"]') as HTMLButtonElement
    expect(importButton.disabled).toBe(false)
    importButton.click()
    await flushPromises()
    expect(api.postForm).toHaveBeenCalledTimes(1)
    const [endpoint, formData] = api.postForm.mock.calls[0] ?? []
    expect(endpoint).toBe('/master-data/uom/import')
    expect(formData).toBeInstanceOf(FormData)
    expect(bodyFind('[data-testid="import-result"]')?.textContent).toContain('Imported: 2')
    expect(wrapper.emitted('committed')).toBeTruthy()
    wrapper.unmount()
  })

  it('falls back to the inline CSV template when no endpoint is configured', async () => {
    const api = makeApi()
    const wrapper = mountDialog(api, {
      templateEndpoint: undefined,
      templateFilename: undefined,
      template: { filename: 'uom_template.csv', csv: 'unit_code,unit_name\nm,Metre\n' },
    })
    await flushPromises()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    ;(bodyFind('[data-testid="download-template"]') as HTMLButtonElement).click()
    await flushPromises()
    expect(api.download).not.toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
    wrapper.unmount()
  })
})
